package basic_validation_test

import (
	"testing"
	"time"

	"github.com/bufbuild/protovalidate-go"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"google.golang.org/protobuf/types/known/durationpb"
	"google.golang.org/protobuf/types/known/timestamppb"

	pb "github.com/buck2-protobuf/examples/modern/validation/basic"
)

func TestModernValidationExamples(t *testing.T) {
	// Create protovalidate validator (reusable for performance)
	validator, err := protovalidate.New()
	require.NoError(t, err, "Failed to create protovalidate validator")

	t.Run("ValidUser", func(t *testing.T) {
		user := createValidUser()
		err := validator.Validate(user)
		assert.NoError(t, err, "Valid user should pass validation")
	})

	t.Run("InvalidEmail", func(t *testing.T) {
		user := createValidUser()
		user.Email = "invalid-email"

		err := validator.Validate(user)
		assert.Error(t, err, "Invalid email should fail validation")
		assert.Contains(t, err.Error(), "email", "Error should mention email field")
	})

	t.Run("InvalidAge", func(t *testing.T) {
		user := createValidUser()
		user.Age = 5 // Too young

		err := validator.Validate(user)
		assert.Error(t, err, "Age below 13 should fail validation")
		assert.Contains(t, err.Error(), "age", "Error should mention age field")
	})

	t.Run("InvalidUsername", func(t *testing.T) {
		user := createValidUser()
		user.Username = "ab" // Too short

		err := validator.Validate(user)
		assert.Error(t, err, "Short username should fail validation")
		assert.Contains(t, err.Error(), "username", "Error should mention username field")
	})

	t.Run("InvalidPhoneNumber", func(t *testing.T) {
		user := createValidUser()
		user.Phone = "123-456-7890" // Wrong format

		err := validator.Validate(user)
		assert.Error(t, err, "Invalid phone format should fail validation")
		assert.Contains(t, err.Error(), "phone", "Error should mention phone field")
	})

	t.Run("NoRoles", func(t *testing.T) {
		user := createValidUser()
		user.Roles = []pb.UserRole{} // Empty roles

		err := validator.Validate(user)
		assert.Error(t, err, "Empty roles should fail validation")
		assert.Contains(t, err.Error(), "roles", "Error should mention roles field")
	})

	t.Run("InvalidEnumValue", func(t *testing.T) {
		user := createValidUser()
		user.Status = pb.UserStatus_USER_STATUS_UNSPECIFIED

		err := validator.Validate(user)
		assert.Error(t, err, "Unspecified status should fail with defined_only constraint")
	})
}

func TestCreateUserRequestValidation(t *testing.T) {
	validator, err := protovalidate.New()
	require.NoError(t, err)

	t.Run("ValidCreateRequest", func(t *testing.T) {
		request := &pb.CreateUserRequest{
			User:            createValidUser(),
			Password:        "SecurePass123!",
			PasswordConfirm: "SecurePass123!",
			AcceptTerms:     true,
		}

		err := validator.Validate(request)
		assert.NoError(t, err, "Valid create request should pass validation")
	})

	t.Run("WeakPassword", func(t *testing.T) {
		request := &pb.CreateUserRequest{
			User:            createValidUser(),
			Password:        "weak", // Too weak
			PasswordConfirm: "weak",
			AcceptTerms:     true,
		}

		err := validator.Validate(request)
		assert.Error(t, err, "Weak password should fail validation")
		assert.Contains(t, err.Error(), "password", "Error should mention password requirements")
	})

	t.Run("TermsNotAccepted", func(t *testing.T) {
		request := &pb.CreateUserRequest{
			User:            createValidUser(),
			Password:        "SecurePass123!",
			PasswordConfirm: "SecurePass123!",
			AcceptTerms:     false, // Must be true
		}

		err := validator.Validate(request)
		assert.Error(t, err, "Terms not accepted should fail validation")
		assert.Contains(t, err.Error(), "accept_terms", "Error should mention terms acceptance")
	})
}

func TestUpdateUserRequestValidation(t *testing.T) {
	validator, err := protovalidate.New()
	require.NoError(t, err)

	t.Run("ValidUpdateRequest", func(t *testing.T) {
		request := &pb.UpdateUserRequest{
			UserId:   123,
			Email:    stringPtr("newemail@example.com"),
			Username: stringPtr("newusername"),
			Age:      int32Ptr(25),
		}

		err := validator.Validate(request)
		assert.NoError(t, err, "Valid update request should pass validation")
	})

	t.Run("InvalidUserId", func(t *testing.T) {
		request := &pb.UpdateUserRequest{
			UserId: 0, // Invalid ID
			Email:  stringPtr("newemail@example.com"),
		}

		err := validator.Validate(request)
		assert.Error(t, err, "Invalid user ID should fail validation")
	})

	t.Run("PartialUpdateValid", func(t *testing.T) {
		request := &pb.UpdateUserRequest{
			UserId: 123,
			Email:  stringPtr("newemail@example.com"),
			// Other fields omitted - should be fine for partial updates
		}

		err := validator.Validate(request)
		assert.NoError(t, err, "Partial update should pass validation")
	})
}

func TestValidationExamplePatterns(t *testing.T) {
	validator, err := protovalidate.New()
	require.NoError(t, err)

	t.Run("ValidExample", func(t *testing.T) {
		example := &pb.ValidationExample{
			RequiredString:   "required value",
			OptionalString:   "optional",
			PatternString:    "ABC",
			PositiveInt:      42,
			RangeInt:         50,
			PositiveDouble:   3.14,
			NonEmptyList:     []string{"item1", "item2"},
			SizeLimitedList:  []string{"item1"},
			RequiredMap:      map[string]string{"key": "value"},
			NonEmptyBytes:    []byte("data"),
			SizeLimitedBytes: []byte("small"),
			PositiveDuration: durationpb.New(time.Hour),
			FutureTimestamp:  timestamppb.New(time.Now().Add(time.Hour)),
		}

		err := validator.Validate(example)
		assert.NoError(t, err, "Valid example should pass all constraints")
	})

	t.Run("InvalidPatterns", func(t *testing.T) {
		// Test pattern constraint
		example := &pb.ValidationExample{
			RequiredString:   "required value",
			PatternString:    "abc", // Should be uppercase
			PositiveInt:      1,
			RangeInt:         50,
			PositiveDouble:   1.0,
			NonEmptyList:     []string{"item1"},
			SizeLimitedList:  []string{"item1"},
			RequiredMap:      map[string]string{"key": "value"},
			NonEmptyBytes:    []byte("data"),
			SizeLimitedBytes: []byte("small"),
			PositiveDuration: durationpb.New(time.Hour),
			FutureTimestamp:  timestamppb.New(time.Now().Add(time.Hour)),
		}

		err := validator.Validate(example)
		assert.Error(t, err, "Invalid pattern should fail validation")
		assert.Contains(t, err.Error(), "pattern", "Error should mention pattern constraint")
	})

	t.Run("EmptyRequiredFields", func(t *testing.T) {
		example := &pb.ValidationExample{
			RequiredString: "", // Empty required string
			PatternString:  "ABC",
			PositiveInt:    1,
			RangeInt:       50,
			PositiveDouble: 1.0,
			NonEmptyList:   []string{},          // Empty list
			RequiredMap:    map[string]string{}, // Empty map
			NonEmptyBytes:  []byte{},            // Empty bytes
		}

		err := validator.Validate(example)
		assert.Error(t, err, "Empty required fields should fail validation")
	})
}

func TestUserProfileValidation(t *testing.T) {
	validator, err := protovalidate.New()
	require.NoError(t, err)

	t.Run("ValidProfile", func(t *testing.T) {
		profile := &pb.UserProfile{
			DisplayName: "John Doe",
			Bio:         "Software Engineer",
			Website:     "https://johndoe.com",
			Location:    "San Francisco, CA",
			AvatarUrl:   "https://avatars.example.com/johndoe.jpg",
		}

		err := validator.Validate(profile)
		assert.NoError(t, err, "Valid profile should pass validation")
	})

	t.Run("InvalidWebsiteURL", func(t *testing.T) {
		profile := &pb.UserProfile{
			DisplayName: "John Doe",
			Website:     "not-a-url", // Invalid URL
		}

		err := validator.Validate(profile)
		assert.Error(t, err, "Invalid website URL should fail validation")
		assert.Contains(t, err.Error(), "website", "Error should mention website field")
	})

	t.Run("InsecureAvatarURL", func(t *testing.T) {
		profile := &pb.UserProfile{
			DisplayName: "John Doe",
			AvatarUrl:   "http://insecure.example.com/avatar.jpg", // HTTP instead of HTTPS
		}

		err := validator.Validate(profile)
		assert.Error(t, err, "Non-HTTPS avatar URL should fail validation")
		assert.Contains(t, err.Error(), "avatar_url", "Error should mention avatar URL requirement")
	})

	t.Run("OptionalFieldsCanBeEmpty", func(t *testing.T) {
		profile := &pb.UserProfile{
			// All fields optional and empty
		}

		err := validator.Validate(profile)
		assert.NoError(t, err, "Empty optional fields should pass validation")
	})
}

func BenchmarkValidation(b *testing.B) {
	validator, err := protovalidate.New()
	require.NoError(b, err)

	user := createValidUser()

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			_ = validator.Validate(user)
		}
	})
}

func BenchmarkValidationWithErrors(b *testing.B) {
	validator, err := protovalidate.New()
	require.NoError(b, err)

	user := createValidUser()
	user.Email = "invalid-email" // Force validation error

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			_ = validator.Validate(user)
		}
	})
}

// Helper functions

func createValidUser() *pb.User {
	return &pb.User{
		Id:       123,
		Email:    "john.doe@example.com",
		Username: "johndoe",
		Age:      30,
		Phone:    "+1234567890",
		Profile: &pb.UserProfile{
			DisplayName: "John Doe",
			Bio:         "Software Engineer",
			Website:     "https://johndoe.com",
			Location:    "San Francisco, CA",
			AvatarUrl:   "https://avatars.example.com/johndoe.jpg",
		},
		Roles:  []pb.UserRole{pb.UserRole_USER_ROLE_USER},
		Status: pb.UserStatus_USER_STATUS_ACTIVE,
	}
}

func stringPtr(s string) *string {
	return &s
}

func int32Ptr(i int32) *int32 {
	return &i
}
