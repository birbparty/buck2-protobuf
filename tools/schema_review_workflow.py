#!/usr/bin/env python3
"""
Schema Review Workflow for Buck2 Protobuf.

This module provides the review workflow engine that manages schema review
requests, approval tracking, and reviewer notifications for team coordination.
"""

import argparse
import json
import os
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any
import logging

# Local imports
from .bsr_auth import BSRAuthenticator, BSRCredentials
from .bsr_teams import BSRTeamManager
from .schema_governance_engine import SchemaChange, GovernanceConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ReviewRequest:
    """Represents a schema review request."""
    id: str
    proto_target: str
    reviewers: List[str]
    approval_count: int
    review_checks: List[str]
    created_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    created_by: Optional[str] = None
    description: Optional[str] = None
    auto_approve_minor: bool = False
    require_breaking_approval: bool = True
    status: str = "pending"  # "pending", "approved", "rejected", "cancelled"
    approvals: List[Dict[str, Any]] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalStatus:
    """Represents the approval status of a review request."""
    review_id: str
    is_approved: bool
    approval_count: int
    required_count: int
    approvers: List[str]
    pending_reviewers: List[str]
    last_updated: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))


@dataclass
class ReviewComment:
    """Represents a comment on a review request."""
    id: str
    review_id: str
    author: str
    content: str
    timestamp: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    comment_type: str = "general"  # "general", "approval", "rejection", "question"


class ReviewWorkflowError(Exception):
    """Review workflow operation failed."""
    pass


class SchemaReviewWorkflow:
    """
    Schema review workflow management system.
    
    Provides centralized management of review requests, approval tracking,
    and reviewer notification for schema governance workflows.
    """
    
    def __init__(self, 
                 storage_dir: Union[str, Path] = None,
                 team_manager: Optional[BSRTeamManager] = None,
                 bsr_authenticator: Optional[BSRAuthenticator] = None,
                 verbose: bool = False):
        """
        Initialize Schema Review Workflow.
        
        Args:
            storage_dir: Directory for review workflow storage
            team_manager: BSR team manager instance
            bsr_authenticator: BSR authentication instance
            verbose: Enable verbose logging
        """
        if storage_dir is None:
            storage_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'review-workflow'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        
        # Storage files
        self.reviews_file = self.storage_dir / "review_requests.json"
        self.approvals_file = self.storage_dir / "review_approvals.json"
        self.comments_file = self.storage_dir / "review_comments.json"
        self.notifications_file = self.storage_dir / "notifications.json"
        
        # Dependencies
        self.team_manager = team_manager or BSRTeamManager(verbose=verbose)
        self.bsr_authenticator = bsr_authenticator or BSRAuthenticator(verbose=verbose)
        
        # Initialize storage
        self._init_storage()
        
        logger.info(f"Schema Review Workflow initialized")

    def _init_storage(self) -> None:
        """Initialize storage files."""
        for file_path in [self.reviews_file, self.approvals_file, self.comments_file, self.notifications_file]:
            if not file_path.exists():
                with open(file_path, 'w') as f:
                    json.dump({}, f)

    def _load_reviews(self) -> Dict[str, ReviewRequest]:
        """Load review requests from storage."""
        try:
            with open(self.reviews_file, 'r') as f:
                reviews_data = json.load(f)
            
            reviews = {}
            for review_id, review_data in reviews_data.items():
                reviews[review_id] = ReviewRequest(**review_data)
            
            return reviews
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_reviews(self, reviews: Dict[str, ReviewRequest]) -> None:
        """Save review requests to storage."""
        try:
            reviews_data = {}
            for review_id, review in reviews.items():
                reviews_data[review_id] = asdict(review)
            
            with open(self.reviews_file, 'w') as f:
                json.dump(reviews_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save reviews: {e}")
            raise ReviewWorkflowError(f"Failed to save reviews: {e}")

    def _load_comments(self) -> Dict[str, List[ReviewComment]]:
        """Load review comments from storage."""
        try:
            with open(self.comments_file, 'r') as f:
                comments_data = json.load(f)
            
            comments = {}
            for review_id, comment_list in comments_data.items():
                comments[review_id] = [ReviewComment(**comment_data) for comment_data in comment_list]
            
            return comments
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_comments(self, comments: Dict[str, List[ReviewComment]]) -> None:
        """Save review comments to storage."""
        try:
            comments_data = {}
            for review_id, comment_list in comments.items():
                comments_data[review_id] = [asdict(comment) for comment in comment_list]
            
            with open(self.comments_file, 'w') as f:
                json.dump(comments_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save comments: {e}")

    def create_review_request(self,
                            proto_target: str,
                            reviewers: List[str],
                            approval_count: int = 1,
                            review_checks: List[str] = None,
                            auto_approve_minor: bool = False,
                            require_breaking_approval: bool = True,
                            description: Optional[str] = None,
                            created_by: Optional[str] = None) -> ReviewRequest:
        """
        Create a new schema review request.
        
        Args:
            proto_target: Proto library target to review
            reviewers: List of required reviewers (teams/users)
            approval_count: Number of approvals required
            review_checks: List of validation checks to run
            auto_approve_minor: Whether to auto-approve minor changes
            require_breaking_approval: Whether breaking changes require approval
            description: Optional review description
            created_by: Username of review creator
            
        Returns:
            Created ReviewRequest
            
        Raises:
            ReviewWorkflowError: If request creation fails
        """
        # Generate unique ID
        review_id = str(uuid.uuid4())[:8]
        
        # Validate reviewers
        if not reviewers:
            raise ReviewWorkflowError("At least one reviewer is required")
        
        # Expand team reviewers to individual members
        expanded_reviewers = self._expand_team_reviewers(reviewers)
        
        # Create review request
        review_request = ReviewRequest(
            id=review_id,
            proto_target=proto_target,
            reviewers=expanded_reviewers,
            approval_count=approval_count,
            review_checks=review_checks or [],
            auto_approve_minor=auto_approve_minor,
            require_breaking_approval=require_breaking_approval,
            description=description,
            created_by=created_by
        )
        
        # Save to storage
        reviews = self._load_reviews()
        reviews[review_id] = review_request
        self._save_reviews(reviews)
        
        logger.info(f"Created review request {review_id} for {proto_target}")
        
        # Send notifications to reviewers
        self._notify_reviewers(review_request, "review_requested")
        
        return review_request

    def create_or_get_review_request(self,
                                   proto_target: str,
                                   reviewers: List[str],
                                   approval_count: int = 1,
                                   review_checks: List[str] = None,
                                   auto_approve_minor: bool = False,
                                   require_breaking_approval: bool = True) -> ReviewRequest:
        """
        Create a review request or return existing pending one.
        
        Args:
            proto_target: Proto library target
            reviewers: Required reviewers
            approval_count: Number of approvals required
            review_checks: Validation checks to run
            auto_approve_minor: Auto-approve minor changes
            require_breaking_approval: Require breaking approval
            
        Returns:
            ReviewRequest (existing or newly created)
        """
        # Check for existing pending review
        existing_review = self._find_pending_review(proto_target)
        if existing_review:
            logger.info(f"Found existing review request {existing_review.id} for {proto_target}")
            return existing_review
        
        # Create new review request
        return self.create_review_request(
            proto_target=proto_target,
            reviewers=reviewers,
            approval_count=approval_count,
            review_checks=review_checks,
            auto_approve_minor=auto_approve_minor,
            require_breaking_approval=require_breaking_approval
        )

    def approve_review(self,
                      review_id: str,
                      reviewer: str,
                      comment: Optional[str] = None) -> bool:
        """
        Approve a review request.
        
        Args:
            review_id: Review request ID
            reviewer: Username of reviewer
            comment: Optional approval comment
            
        Returns:
            True if approval was successful
            
        Raises:
            ReviewWorkflowError: If approval fails
        """
        reviews = self._load_reviews()
        if review_id not in reviews:
            raise ReviewWorkflowError(f"Review request {review_id} not found")
        
        review = reviews[review_id]
        
        # Check if reviewer is authorized
        if not self._is_authorized_reviewer(reviewer, review.reviewers):
            raise ReviewWorkflowError(f"User {reviewer} is not authorized to review {review_id}")
        
        # Check if already approved by this reviewer
        existing_approval = next(
            (approval for approval in review.approvals if approval['reviewer'] == reviewer),
            None
        )
        
        if existing_approval:
            logger.warning(f"Review {review_id} already approved by {reviewer}")
            return False
        
        # Add approval
        approval = {
            "reviewer": reviewer,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "comment": comment
        }
        review.approvals.append(approval)
        
        # Add comment if provided
        if comment:
            self._add_comment(review_id, reviewer, comment, "approval")
        
        # Check if review is now fully approved
        if len(review.approvals) >= review.approval_count:
            review.status = "approved"
            logger.info(f"Review {review_id} fully approved with {len(review.approvals)} approvals")
            self._notify_reviewers(review, "review_approved")
        else:
            logger.info(f"Review {review_id} approved by {reviewer} ({len(review.approvals)}/{review.approval_count})")
        
        # Save changes
        reviews[review_id] = review
        self._save_reviews(reviews)
        
        return True

    def reject_review(self,
                     review_id: str,
                     reviewer: str,
                     reason: str) -> bool:
        """
        Reject a review request.
        
        Args:
            review_id: Review request ID
            reviewer: Username of reviewer
            reason: Reason for rejection
            
        Returns:
            True if rejection was successful
            
        Raises:
            ReviewWorkflowError: If rejection fails
        """
        reviews = self._load_reviews()
        if review_id not in reviews:
            raise ReviewWorkflowError(f"Review request {review_id} not found")
        
        review = reviews[review_id]
        
        # Check if reviewer is authorized
        if not self._is_authorized_reviewer(reviewer, review.reviewers):
            raise ReviewWorkflowError(f"User {reviewer} is not authorized to review {review_id}")
        
        # Update review status
        review.status = "rejected"
        
        # Add rejection comment
        self._add_comment(review_id, reviewer, reason, "rejection")
        
        # Save changes
        reviews[review_id] = review
        self._save_reviews(reviews)
        
        logger.info(f"Review {review_id} rejected by {reviewer}: {reason}")
        
        # Notify stakeholders
        self._notify_reviewers(review, "review_rejected", {"reviewer": reviewer, "reason": reason})
        
        return True

    def check_approval_status(self, review_id: str) -> ApprovalStatus:
        """
        Check the approval status of a review request.
        
        Args:
            review_id: Review request ID
            
        Returns:
            ApprovalStatus with current status
            
        Raises:
            ReviewWorkflowError: If review not found
        """
        reviews = self._load_reviews()
        if review_id not in reviews:
            raise ReviewWorkflowError(f"Review request {review_id} not found")
        
        review = reviews[review_id]
        
        # Get list of approvers
        approvers = [approval['reviewer'] for approval in review.approvals]
        
        # Determine pending reviewers
        pending_reviewers = [
            reviewer for reviewer in review.reviewers 
            if reviewer not in approvers
        ]
        
        return ApprovalStatus(
            review_id=review_id,
            is_approved=len(review.approvals) >= review.approval_count,
            approval_count=len(review.approvals),
            required_count=review.approval_count,
            approvers=approvers,
            pending_reviewers=pending_reviewers
        )

    def add_comment(self,
                   review_id: str,
                   author: str,
                   content: str,
                   comment_type: str = "general") -> ReviewComment:
        """
        Add a comment to a review request.
        
        Args:
            review_id: Review request ID
            author: Comment author username
            content: Comment content
            comment_type: Type of comment
            
        Returns:
            Created ReviewComment
            
        Raises:
            ReviewWorkflowError: If comment addition fails
        """
        reviews = self._load_reviews()
        if review_id not in reviews:
            raise ReviewWorkflowError(f"Review request {review_id} not found")
        
        return self._add_comment(review_id, author, content, comment_type)

    def list_pending_reviews(self, reviewer: Optional[str] = None) -> List[ReviewRequest]:
        """
        List pending review requests.
        
        Args:
            reviewer: Optional filter by reviewer
            
        Returns:
            List of pending ReviewRequest objects
        """
        reviews = self._load_reviews()
        pending_reviews = []
        
        for review in reviews.values():
            if review.status != "pending":
                continue
            
            if reviewer is None:
                pending_reviews.append(review)
            elif reviewer in review.reviewers:
                # Check if this reviewer hasn't approved yet
                approvers = [approval['reviewer'] for approval in review.approvals]
                if reviewer not in approvers:
                    pending_reviews.append(review)
        
        # Sort by creation time
        pending_reviews.sort(key=lambda r: r.created_at)
        
        return pending_reviews

    def get_review_details(self, review_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a review request.
        
        Args:
            review_id: Review request ID
            
        Returns:
            Dictionary with review details
            
        Raises:
            ReviewWorkflowError: If review not found
        """
        reviews = self._load_reviews()
        if review_id not in reviews:
            raise ReviewWorkflowError(f"Review request {review_id} not found")
        
        review = reviews[review_id]
        comments = self._load_comments().get(review_id, [])
        
        return {
            "review": asdict(review),
            "comments": [asdict(comment) for comment in comments],
            "approval_status": asdict(self.check_approval_status(review_id))
        }

    def notify_teams(self,
                    review_id: str,
                    teams: List[str],
                    message: str) -> None:
        """
        Notify teams about a review request.
        
        Args:
            review_id: Review request ID
            teams: List of teams to notify
            message: Notification message
        """
        notification_data = {
            "review_id": review_id,
            "teams": teams,
            "message": message,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        # Load existing notifications
        try:
            with open(self.notifications_file, 'r') as f:
                notifications = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            notifications = {}
        
        # Add new notification
        notification_id = str(uuid.uuid4())[:8]
        notifications[notification_id] = notification_data
        
        # Save notifications
        try:
            with open(self.notifications_file, 'w') as f:
                json.dump(notifications, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save notifications: {e}")
        
        logger.info(f"Notification sent to teams {teams} for review {review_id}")

    def _expand_team_reviewers(self, reviewers: List[str]) -> List[str]:
        """Expand team references to individual team members."""
        expanded = []
        
        for reviewer in reviewers:
            if reviewer.startswith('@'):
                # Team reference
                team_name = reviewer[1:]
                team_info = self.team_manager.get_team_info(team_name)
                if team_info:
                    # Add all team members with appropriate roles
                    for username, member_info in team_info['members'].items():
                        if member_info['role'] in ['maintainer', 'admin']:
                            expanded.append(username)
                else:
                    logger.warning(f"Team {team_name} not found, keeping as-is")
                    expanded.append(reviewer)
            else:
                # Individual reviewer
                expanded.append(reviewer)
        
        return list(set(expanded))  # Remove duplicates

    def _is_authorized_reviewer(self, reviewer: str, authorized_reviewers: List[str]) -> bool:
        """Check if a user is authorized to review."""
        return reviewer in authorized_reviewers

    def _find_pending_review(self, proto_target: str) -> Optional[ReviewRequest]:
        """Find existing pending review for a proto target."""
        reviews = self._load_reviews()
        
        for review in reviews.values():
            if review.proto_target == proto_target and review.status == "pending":
                return review
        
        return None

    def _add_comment(self,
                    review_id: str,
                    author: str,
                    content: str,
                    comment_type: str = "general") -> ReviewComment:
        """Internal method to add a comment."""
        comment_id = str(uuid.uuid4())[:8]
        comment = ReviewComment(
            id=comment_id,
            review_id=review_id,
            author=author,
            content=content,
            comment_type=comment_type
        )
        
        # Load existing comments
        comments = self._load_comments()
        if review_id not in comments:
            comments[review_id] = []
        
        comments[review_id].append(comment)
        self._save_comments(comments)
        
        logger.info(f"Added comment to review {review_id} by {author}")
        
        return comment

    def _notify_reviewers(self,
                         review: ReviewRequest,
                         event_type: str,
                         extra_data: Dict[str, Any] = None) -> None:
        """Send notifications to reviewers."""
        # In a full implementation, this would send actual notifications
        # (email, Slack, webhooks, etc.) to reviewers
        
        notification_data = {
            "event_type": event_type,
            "review_id": review.id,
            "proto_target": review.proto_target,
            "reviewers": review.reviewers,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        if extra_data:
            notification_data.update(extra_data)
        
        logger.info(f"Notification sent for {event_type}: review {review.id}")


def main():
    """Main entry point for review workflow testing."""
    parser = argparse.ArgumentParser(description="Schema Review Workflow")
    parser.add_argument("--storage-dir", help="Storage directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create review
    create_parser = subparsers.add_parser("create", help="Create review request")
    create_parser.add_argument("--target", required=True, help="Proto target to review")
    create_parser.add_argument("--reviewers", nargs="+", required=True, help="Required reviewers")
    create_parser.add_argument("--approval-count", type=int, default=1, help="Number of approvals required")
    create_parser.add_argument("--description", help="Review description")
    
    # Approve review
    approve_parser = subparsers.add_parser("approve", help="Approve review request")
    approve_parser.add_argument("review_id", help="Review ID to approve")
    approve_parser.add_argument("--reviewer", required=True, help="Reviewer username")
    approve_parser.add_argument("--comment", help="Approval comment")
    
    # Reject review
    reject_parser = subparsers.add_parser("reject", help="Reject review request")
    reject_parser.add_argument("review_id", help="Review ID to reject")
    reject_parser.add_argument("--reviewer", required=True, help="Reviewer username")
    reject_parser.add_argument("--reason", required=True, help="Rejection reason")
    
    # List reviews
    list_parser = subparsers.add_parser("list", help="List pending reviews")
    list_parser.add_argument("--reviewer", help="Filter by reviewer")
    
    # Review status
    status_parser = subparsers.add_parser("status", help="Check review status")
    status_parser.add_argument("review_id", help="Review ID to check")
    
    # Add comment
    comment_parser = subparsers.add_parser("comment", help="Add comment to review")
    comment_parser.add_argument("review_id", help="Review ID")
    comment_parser.add_argument("--author", required=True, help="Comment author")
    comment_parser.add_argument("--content", required=True, help="Comment content")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        workflow = SchemaReviewWorkflow(
            storage_dir=args.storage_dir,
            verbose=args.verbose
        )
        
        if args.command == "create":
            review = workflow.create_review_request(
                proto_target=args.target,
                reviewers=args.reviewers,
                approval_count=args.approval_count,
                description=args.description
            )
            print(f"✅ Created review request {review.id} for {args.target}")
            print(f"   Reviewers: {', '.join(review.reviewers)}")
            print(f"   Required approvals: {review.approval_count}")
        
        elif args.command == "approve":
            success = workflow.approve_review(
                review_id=args.review_id,
                reviewer=args.reviewer,
                comment=args.comment
            )
            if success:
                print(f"✅ Review {args.review_id} approved by {args.reviewer}")
            else:
                print(f"⚠️  Review {args.review_id} was already approved by {args.reviewer}")
        
        elif args.command == "reject":
            success = workflow.reject_review(
                review_id=args.review_id,
                reviewer=args.reviewer,
                reason=args.reason
            )
            if success:
                print(f"❌ Review {args.review_id} rejected by {args.reviewer}")
                print(f"   Reason: {args.reason}")
        
        elif args.command == "list":
            reviews = workflow.list_pending_reviews(reviewer=args.reviewer)
            if reviews:
                print(f"Pending reviews ({len(reviews)}):")
                for review in reviews:
                    status = workflow.check_approval_status(review.id)
                    print(f"  {review.id}: {review.proto_target}")
                    print(f"    Created: {review.created_at}")
                    print(f"    Approvals: {status.approval_count}/{status.required_count}")
                    if status.approvers:
                        print(f"    Approved by: {', '.join(status.approvers)}")
                    if status.pending_reviewers:
                        print(f"    Pending: {', '.join(status.pending_reviewers)}")
                    print()
            else:
                print("No pending reviews")
        
        elif args.command == "status":
            status = workflow.check_approval_status(args.review_id)
            print(f"Review {args.review_id} status:")
            print(f"  Approved: {status.is_approved}")
            print(f"  Approvals: {status.approval_count}/{status.required_count}")
            if status.approvers:
                print(f"  Approved by: {', '.join(status.approvers)}")
            if status.pending_reviewers:
                print(f"  Pending reviewers: {', '.join(status.pending_reviewers)}")
        
        elif args.command == "comment":
            comment = workflow.add_comment(
                review_id=args.review_id,
                author=args.author,
                content=args.content
            )
            print(f"✅ Added comment {comment.id} to review {args.review_id}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
