package main

import (
	"errors"
	"testing"
)

func TestNewErrorwithSourceLocfMessage(t *testing.T) {
	err := newErrorwithSourceLocf("a%sc", "b")
	if err.Error() != "errors_test.go:9: abc" {
		t.Errorf("Error message incorrect. Got: %s", err.Error())
	}
}

func TestWrapErrorwithSourceLocfMessage(t *testing.T) {
	cause := errors.New("someCause")
	err := wrapErrorwithSourceLocf(cause, "a%sc", "b")
	if err.Error() != "errors_test.go:17: abc: someCause" {
		t.Errorf("Error message incorrect. Got: %s", err.Error())
	}
}

func TestNewUserErrorf(t *testing.T) {
	err := newUserErrorf("a%sc", "b")
	if err.Error() != "abc" {
		t.Errorf("Error message incorrect. Got: %s", err.Error())
	}
}
