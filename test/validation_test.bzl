"""Test validation for proto_library rule."""

load("//rules:proto.bzl", "proto_library")

# Test case for validation - this should fail if we tried to build it
def test_empty_srcs():
    proto_library(
        name = "empty_proto_test",
        srcs = [],  # This should fail validation
        visibility = ["//test:__pkg__"],
    )

def test_non_proto_file():
    proto_library(
        name = "invalid_file_test", 
        srcs = ["test_data.json"],  # This should fail validation
        visibility = ["//test:__pkg__"],
    )
