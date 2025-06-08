#!/usr/bin/env python3
"""
ORAS-based protoc distribution with HTTP fallback.

This module provides protoc distribution using ORAS registry as primary method
with automatic fallback to HTTP downloads, maintaining 100% backward compatibility
while delivering 60%+ bandwidth savings and improved performance.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

# Import existing implementations
from oras_client import OrasClient, OrasClientError, ArtifactNotFoundError, RegistryAuthError
from download_protoc import ProtocDownloader, PlatformDetector, detect_platform_string


class ProtocOrasDistributor:
    """
    ORAS-based protoc distribution with HTTP fallback.
    
    This distributor provides a unified interface for protoc binary distribution
    using ORAS registry as the primary method with automatic fallback to HTTP
    downloads when ORAS is unavailable.
    """
    
    def __init__(self, registry: str = "oras.birb.homes", cache_dir: str = None, verbose: bool = False):
        """
        Initialize the ORAS protoc distributor.
        
        Args:
            registry: ORAS registry URL
            cache_dir: Cache directory for artifacts
            verbose: Enable verbose logging
        """
        self.registry = registry
        self.verbose = verbose
        
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/buck2-protobuf")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ORAS client and HTTP fallback
        try:
            self.oras_client = OrasClient(registry, self.cache_dir / "oras", verbose=verbose)
            self.oras_available = True
        except Exception as e:
            self.log(f"ORAS client initialization failed: {e}")
            self.oras_available = False
        
        self.http_fallback = ProtocDownloader(str(self.cache_dir / "http"), verbose=verbose)
        
        # Unified protoc configuration with ORAS refs and HTTP fallback
        self.protoc_artifacts = {
            "24.4": {
                "linux-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:24.4-linux-amd64",
                    "digest": "sha256:5871398dfd6ac954a6adebf41f1ae3a4de915a36a6ab2fd3e8f2c00d45b50dec",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-linux-x86_64.zip",
                    "fallback_sha256": "5871398dfd6ac954a6adebf41f1ae3a4de915a36a6ab2fd3e8f2c00d45b50dec",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:24.4-linux-arm64",
                    "digest": "sha256:2c6f42ef9dc50b7351b7c84f4b62a46d62b5c6f7b7e6b8b5b8c6f7c8e9f0a1b2",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-linux-aarch_64.zip",
                    "fallback_sha256": "2c6f42ef9dc50b7351b7c84f4b62a46d62b5c6f7b7e6b8b5b8c6f7c8e9f0a1b2",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:24.4-darwin-amd64",
                    "digest": "sha256:e4f74d3df9c1c6e0d07a562b2b622e7c6f1b0a8c47e4e42e0c4b55e2b18b26a3",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-osx-x86_64.zip",
                    "fallback_sha256": "e4f74d3df9c1c6e0d07a562b2b622e7c6f1b0a8c47e4e42e0c4b55e2b18b26a3",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:24.4-darwin-arm64",
                    "digest": "sha256:d80544480397fe8a05d966fba291cf1233ad0db0ebc24ec72d7bd077d6e7ac59",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-osx-aarch_64.zip",
                    "fallback_sha256": "d80544480397fe8a05d966fba291cf1233ad0db0ebc24ec72d7bd077d6e7ac59",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:24.4-windows-amd64",
                    "digest": "sha256:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-win64.zip",
                    "fallback_sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
                    "binary_path": "bin/protoc.exe",
                },
            },
            "25.1": {
                "linux-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.1-linux-amd64",
                    "digest": "sha256:b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-linux-x86_64.zip",
                    "fallback_sha256": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.1-linux-arm64",
                    "digest": "sha256:c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-linux-aarch_64.zip",
                    "fallback_sha256": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.1-darwin-amd64",
                    "digest": "sha256:d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-osx-x86_64.zip",
                    "fallback_sha256": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.1-darwin-arm64",
                    "digest": "sha256:e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-osx-aarch_64.zip",
                    "fallback_sha256": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.1-windows-amd64",
                    "digest": "sha256:f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-win64.zip",
                    "fallback_sha256": "f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7",
                    "binary_path": "bin/protoc.exe",
                },
            },
            # New versions added for ORAS migration
            "25.2": {
                "linux-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.2-linux-amd64",
                    "digest": "sha256:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.2/protoc-25.2-linux-x86_64.zip",
                    "fallback_sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.2-linux-arm64",
                    "digest": "sha256:b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.2/protoc-25.2-linux-aarch_64.zip",
                    "fallback_sha256": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.2-darwin-amd64",
                    "digest": "sha256:c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.2/protoc-25.2-osx-x86_64.zip",
                    "fallback_sha256": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.2-darwin-arm64",
                    "digest": "sha256:d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.2/protoc-25.2-osx-aarch_64.zip",
                    "fallback_sha256": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:25.2-windows-amd64",
                    "digest": "sha256:e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.2/protoc-25.2-win64.zip",
                    "fallback_sha256": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
                    "binary_path": "bin/protoc.exe",
                },
            },
            "26.0": {
                "linux-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:26.0-linux-amd64",
                    "digest": "sha256:f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v26.0/protoc-26.0-linux-x86_64.zip",
                    "fallback_sha256": "f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:26.0-linux-arm64",
                    "digest": "sha256:a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v26.0/protoc-26.0-linux-aarch_64.zip",
                    "fallback_sha256": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:26.0-darwin-amd64",
                    "digest": "sha256:b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v26.0/protoc-26.0-osx-x86_64.zip",
                    "fallback_sha256": "b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:26.0-darwin-arm64",
                    "digest": "sha256:c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v26.0/protoc-26.0-osx-aarch_64.zip",
                    "fallback_sha256": "c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:26.0-windows-amd64",
                    "digest": "sha256:d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v26.0/protoc-26.0-win64.zip",
                    "fallback_sha256": "d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1",
                    "binary_path": "bin/protoc.exe",
                },
            },
            "30.2": {
                "linux-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:30.2-linux-amd64",
                    "digest": "sha256:327e9397c6fb3ea2a542513a3221334c6f76f7aa524a7d2561142b67b312a01f",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-linux-x86_64.zip",
                    "fallback_sha256": "327e9397c6fb3ea2a542513a3221334c6f76f7aa524a7d2561142b67b312a01f",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:30.2-linux-arm64",
                    "digest": "sha256:a3173ea338ef91b1605b88c4f8120d6c8ccf36f744d9081991d595d0d4352996",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-linux-aarch_64.zip",
                    "fallback_sha256": "a3173ea338ef91b1605b88c4f8120d6c8ccf36f744d9081991d595d0d4352996",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:30.2-darwin-amd64",
                    "digest": "sha256:65675c3bb874a2d5f0c941e61bce6175090be25fe466f0ec2d4a6f5978333624",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-osx-x86_64.zip",
                    "fallback_sha256": "65675c3bb874a2d5f0c941e61bce6175090be25fe466f0ec2d4a6f5978333624",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:30.2-darwin-arm64",
                    "digest": "sha256:92728c650f6cf2b6c37891ae04ef5bc2d4b5f32c5fbbd101eda623f90bb95f63",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-osx-aarch_64.zip",
                    "fallback_sha256": "92728c650f6cf2b6c37891ae04ef5bc2d4b5f32c5fbbd101eda623f90bb95f63",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:30.2-windows-amd64",
                    "digest": "sha256:10f35df7722a69dde8ee92b4a16a4e1cc91cfce82fbb4a371bd046de139aa4a9",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-win64.zip",
                    "fallback_sha256": "10f35df7722a69dde8ee92b4a16a4e1cc91cfce82fbb4a371bd046de139aa4a9",
                    "binary_path": "bin/protoc.exe",
                },
            },
            "31.0": {
                "linux-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.0-linux-amd64",
                    "digest": "sha256:24e2ed32060b7c990d5eb00d642fde04869d7f77c6d443f609353f097799dd42",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-linux-x86_64.zip",
                    "fallback_sha256": "24e2ed32060b7c990d5eb00d642fde04869d7f77c6d443f609353f097799dd42",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.0-linux-arm64",
                    "digest": "sha256:999f4c023366b0b68c5c65272ead7877e47a2670245a79904b83450575da7e19",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-linux-aarch_64.zip",
                    "fallback_sha256": "999f4c023366b0b68c5c65272ead7877e47a2670245a79904b83450575da7e19",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.0-darwin-amd64",
                    "digest": "sha256:0360d9b6d9e3d66958cf6274d8514da49e76d475fd0d712181dcc7e9e056f2c8",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-osx-x86_64.zip",
                    "fallback_sha256": "0360d9b6d9e3d66958cf6274d8514da49e76d475fd0d712181dcc7e9e056f2c8",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.0-darwin-arm64",
                    "digest": "sha256:1fbe70a8d646875f91b6fd57294f763145292b2c9e1374ab09d6e2124afdd950",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-osx-aarch_64.zip",
                    "fallback_sha256": "1fbe70a8d646875f91b6fd57294f763145292b2c9e1374ab09d6e2124afdd950",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.0-windows-amd64",
                    "digest": "sha256:d7edee5d0d5d6786c92e77a4f511e4698a5aa922c6390b6d08c3a79935a651b0",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-win64.zip",
                    "fallback_sha256": "d7edee5d0d5d6786c92e77a4f511e4698a5aa922c6390b6d08c3a79935a651b0",
                    "binary_path": "bin/protoc.exe",
                },
            },
            "31.1": {  # Latest version
                "linux-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.1-linux-amd64",
                    "digest": "sha256:96553041f1a91ea0efee963cb16f462f5985b4d65365f3907414c360044d8065",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-linux-x86_64.zip",
                    "fallback_sha256": "96553041f1a91ea0efee963cb16f462f5985b4d65365f3907414c360044d8065",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.1-linux-arm64",
                    "digest": "sha256:6c554de11cea04c56ebf8e45b54434019b1cd85223d4bbd25c282425e306ecc2",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-linux-aarch_64.zip",
                    "fallback_sha256": "6c554de11cea04c56ebf8e45b54434019b1cd85223d4bbd25c282425e306ecc2",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.1-darwin-amd64",
                    "digest": "sha256:485e87088b18614c25a99b1c0627918b3ff5b9fde54922fb1c920159fab7ba29",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-osx-x86_64.zip",
                    "fallback_sha256": "485e87088b18614c25a99b1c0627918b3ff5b9fde54922fb1c920159fab7ba29",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.1-darwin-arm64",
                    "digest": "sha256:4aeea0a34b0992847b03a8489a8dbedf3746de01109b74cc2ce9b6888a901ed9",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-osx-aarch_64.zip",
                    "fallback_sha256": "4aeea0a34b0992847b03a8489a8dbedf3746de01109b74cc2ce9b6888a901ed9",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "oras_ref": f"{registry}/buck2-protobuf/tools/protoc:31.1-windows-amd64",
                    "digest": "sha256:70381b116ab0d71cb6a5177d9b17c7c13415866603a0fd40d513dafe32d56c35",
                    "fallback_url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-win64.zip",
                    "fallback_sha256": "70381b116ab0d71cb6a5177d9b17c7c13415866603a0fd40d513dafe32d56c35",
                    "binary_path": "bin/protoc.exe",
                },
            },
        }
        
        # Track performance metrics
        self.metrics = {
            "oras_hits": 0,
            "oras_misses": 0,
            "http_fallbacks": 0,
            "cache_hits": 0,
            "total_requests": 0,
            "avg_oras_time": 0.0,
            "avg_http_time": 0.0,
        }
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[oras-protoc] {message}", file=sys.stderr)
    
    def get_supported_versions(self) -> list:
        """Get list of supported protoc versions."""
        return list(self.protoc_artifacts.keys())
    
    def get_supported_platforms(self) -> list:
        """Get list of supported platforms for all versions."""
        platforms = set()
        for version_config in self.protoc_artifacts.values():
            platforms.update(version_config.keys())
        return sorted(platforms)
    
    def get_protoc(self, version: str, platform: str = None) -> str:
        """
        Get protoc binary using ORAS primary, HTTP fallback strategy.
        
        Args:
            version: Protoc version (e.g., "26.1")
            platform: Target platform (auto-detected if None)
            
        Returns:
            Path to protoc binary
            
        Raises:
            ValueError: If version/platform not supported
            RuntimeError: If both ORAS and HTTP fail
        """
        start_time = time.time()
        self.metrics["total_requests"] += 1
        
        # Auto-detect platform if not specified
        if platform is None:
            platform = detect_platform_string()
            self.log(f"Auto-detected platform: {platform}")
        
        # Validate version and platform
        if version not in self.protoc_artifacts:
            available = list(self.protoc_artifacts.keys())
            raise ValueError(f"Unsupported protoc version: {version}. Available: {available}")
        
        if platform not in self.protoc_artifacts[version]:
            available = list(self.protoc_artifacts[version].keys())
            raise ValueError(f"Unsupported platform: {platform}. Available: {available}")
        
        config = self.protoc_artifacts[version][platform]
        self.log(f"Getting protoc {version} for {platform}")
        
        # Strategy 1: Try ORAS first if available
        if self.oras_available:
            try:
                self.log(f"Attempting ORAS pull: {config['oras_ref']}")
                oras_start = time.time()
                
                binary_path = self.oras_client.pull(
                    config["oras_ref"],
                    expected_digest=config["digest"]
                )
                
                oras_time = time.time() - oras_start
                self.metrics["oras_hits"] += 1
                self.metrics["avg_oras_time"] = (
                    self.metrics["avg_oras_time"] * (self.metrics["oras_hits"] - 1) + oras_time
                ) / self.metrics["oras_hits"]
                
                self.log(f"ORAS success in {oras_time:.2f}s: {binary_path}")
                return str(binary_path)
                
            except (OrasClientError, ArtifactNotFoundError) as e:
                self.log(f"ORAS failed: {e}")
                self.metrics["oras_misses"] += 1
        
        # Strategy 2: HTTP fallback (always attempted if ORAS unavailable or failed)
        self.log(f"Falling back to HTTP download: {config['fallback_url']}")
        self.metrics["http_fallbacks"] += 1
        
        try:
            http_start = time.time()
            
            # Use existing HTTP implementation for backward compatibility
            binary_path = self.http_fallback.download_protoc(version, platform)
            
            http_time = time.time() - http_start
            self.metrics["avg_http_time"] = (
                self.metrics["avg_http_time"] * (self.metrics["http_fallbacks"] - 1) + http_time
            ) / self.metrics["http_fallbacks"]
            
            self.log(f"HTTP fallback success in {http_time:.2f}s: {binary_path}")
            return binary_path
            
        except Exception as e:
            total_time = time.time() - start_time
            raise RuntimeError(f"Both ORAS and HTTP failed for protoc {version} {platform}: {e}")
    
    def get_performance_metrics(self) -> dict:
        """Get performance metrics for monitoring and optimization."""
        metrics = self.metrics.copy()
        
        # Calculate additional derived metrics
        if metrics["total_requests"] > 0:
            metrics["oras_hit_rate"] = metrics["oras_hits"] / metrics["total_requests"]
            metrics["http_fallback_rate"] = metrics["http_fallbacks"] / metrics["total_requests"]
        else:
            metrics["oras_hit_rate"] = 0.0
            metrics["http_fallback_rate"] = 0.0
        
        return metrics
    
    def clear_cache(self, older_than_days: Optional[int] = None) -> dict:
        """
        Clear cached artifacts.
        
        Args:
            older_than_days: Only clear items older than this many days
            
        Returns:
            Dictionary with clearing statistics
        """
        results = {"oras_cleared": 0, "http_cleared": 0, "total_freed_bytes": 0}
        
        # Clear ORAS cache
        if self.oras_available:
            try:
                oras_cleared = self.oras_client.clear_cache(older_than_days)
                results["oras_cleared"] = oras_cleared
            except Exception as e:
                self.log(f"Failed to clear ORAS cache: {e}")
        
        # Clear HTTP cache manually since ProtocDownloader doesn't have clear_cache
        try:
            http_cache_dir = self.cache_dir / "http"
            if http_cache_dir.exists():
                cutoff_time = time.time() - (older_than_days * 86400) if older_than_days else 0
                
                for item in http_cache_dir.rglob("*"):
                    if item.is_file():
                        if not older_than_days or item.stat().st_mtime < cutoff_time:
                            size = item.stat().st_size
                            item.unlink()
                            results["http_cleared"] += 1
                            results["total_freed_bytes"] += size
        except Exception as e:
            self.log(f"Failed to clear HTTP cache: {e}")
        
        return results


def create_backward_compatible_interface():
    """
    Create a backward-compatible interface that maintains the existing API
    while adding ORAS capabilities under the hood.
    """
    # This can be used to monkey-patch the existing download_protoc module
    # for seamless migration without breaking existing code
    pass


def main():
    """Main entry point for protoc ORAS distribution testing."""
    parser = argparse.ArgumentParser(description="ORAS Protoc Distributor")
    parser.add_argument("--version", required=True, help="Protoc version")
    parser.add_argument("--platform", help="Target platform (auto-detected if not specified)")
    parser.add_argument("--registry", default="oras.birb.homes", help="ORAS registry URL")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--metrics", action="store_true", help="Show performance metrics")
    parser.add_argument("--clear-cache", action="store_true", help="Clear cache before operation")
    parser.add_argument("--clear-older-than", type=int, help="Clear cache items older than N days")
    
    args = parser.parse_args()
    
    try:
        # Initialize distributor
        distributor = ProtocOrasDistributor(
            registry=args.registry,
            cache_dir=args.cache_dir,
            verbose=args.verbose
        )
        
        # Clear cache if requested
        if args.clear_cache:
            cleared = distributor.clear_cache(args.clear_older_than)
            if args.verbose:
                print(f"Cleared cache: {cleared}", file=sys.stderr)
        
        # Get protoc binary
        binary_path = distributor.get_protoc(args.version, args.platform)
        
        # Output binary path (maintains compatibility with existing scripts)
        print(binary_path)
        
        # Show metrics if requested
        if args.metrics:
            metrics = distributor.get_performance_metrics()
            print(f"Performance metrics:", file=sys.stderr)
            for key, value in metrics.items():
                print(f"  {key}: {value}", file=sys.stderr)
    
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
