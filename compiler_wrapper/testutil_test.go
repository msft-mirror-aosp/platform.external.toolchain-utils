package main

import (
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

var crosRootDirFlag = flag.String("crosroot", "", "root dir of the chrome os toolchain")

const mainCc = "main.cc"
const clangX86_64 = "./x86_64-cros-linux-gnu-clang"
const gccX86_64 = "./x86_64-cros-linux-gnu-gcc"
const gccX86_64Eabi = "./x86_64-cros-linux-eabi-gcc"
const gccArmV7 = "./armv7m-cros-linux-gnu-gcc"
const gccArmV7Eabi = "./armv7m-cros-linux-eabi-gcc"
const gccArmV8 = "./armv8m-cros-linux-gnu-gcc"
const gccArmV8Eabi = "./armv8m-cros-linux-eabi-gcc"

const oldHardenedWrapperPathForTest = "/usr/x86_64-pc-linux-gnu/x86_64-cros-linux-gnu/gcc-bin/4.9.x/sysroot_wrapper.hardened"
const oldNonHardenedWrapperPathForTest = "/usr/x86_64-pc-linux-gnu/arm-none-eabi/gcc-bin/4.9.x/sysroot_wrapper"

type testContext struct {
	t       *testing.T
	tempDir string
	env     []string
	cfg     *config
}

func withTestContext(t *testing.T, work func(ctx *testContext)) {
	t.Parallel()
	tempDir, err := ioutil.TempDir("", "compiler_wrapper")
	if err != nil {
		t.Fatalf("Unable to create the temp dir. Error: %s", err)
	}
	defer os.RemoveAll(tempDir)

	ctx := testContext{
		t:       t,
		tempDir: tempDir,
		env:     nil,
		cfg: &config{
			oldWrapperPath:           "FilledLater",
			overrideOldWrapperConfig: true,
		},
	}
	// Note: It's ok to use the hardened wrapper here, as we replace its config
	// on each run.
	ctx.setOldWrapperPath(oldHardenedWrapperPathForTest)

	work(&ctx)
}

var _ env = (*testContext)(nil)

func (ctx *testContext) getenv(key string) string {
	for i := len(ctx.env) - 1; i >= 0; i-- {
		entry := ctx.env[i]
		if strings.HasPrefix(entry, key+"=") {
			return entry[len(key)+1:]
		}
	}
	return ""
}

func (ctx *testContext) environ() []string {
	return ctx.env
}

func (ctx *testContext) getwd() string {
	return ctx.tempDir
}

func (ctx *testContext) must(cmd *command, err error) *command {
	if err != nil {
		ctx.t.Fatalf("Expected no error, but got %s", err)
	}
	return cmd
}

func (ctx *testContext) setOldWrapperPath(chrootPath string) {
	if *crosRootDirFlag != "" {
		ctx.cfg.oldWrapperPath = filepath.Join(*crosRootDirFlag, chrootPath)
	} else {
		ctx.cfg.oldWrapperPath = ""
	}
}

func (ctx *testContext) newCommand(path string, args ...string) *command {
	// Create an empty wrapper at the given path.
	// Needed as we are resolving symlinks which stats the wrapper file.
	ctx.writeFile(path, "")
	return &command{
		path: path,
		args: args,
	}
}

func (ctx *testContext) writeFile(fullFileName string, fileContent string) {
	if !filepath.IsAbs(fullFileName) {
		fullFileName = filepath.Join(ctx.tempDir, fullFileName)
	}
	if err := os.MkdirAll(filepath.Dir(fullFileName), 0777); err != nil {
		ctx.t.Fatal(err)
	}
	if err := ioutil.WriteFile(fullFileName, []byte(fileContent), 0777); err != nil {
		ctx.t.Fatal(err)
	}
}

func (ctx *testContext) symlink(oldname string, newname string) {
	if err := os.MkdirAll(filepath.Dir(newname), 0777); err != nil {
		ctx.t.Fatal(err)
	}
	if err := os.Symlink(oldname, newname); err != nil {
		ctx.t.Fatal(err)
	}
}

func verifyPath(cmd *command, expectedRegex string) error {
	compiledRegex := regexp.MustCompile(matchFullString(expectedRegex))
	if !compiledRegex.MatchString(cmd.path) {
		return fmt.Errorf("path does not match %s. Actual %s", expectedRegex, cmd.path)
	}
	return nil
}

func verifyArgCount(cmd *command, expectedCount int, expectedRegex string) error {
	compiledRegex := regexp.MustCompile(matchFullString(expectedRegex))
	count := 0
	for _, arg := range cmd.args {
		if compiledRegex.MatchString(arg) {
			count++
		}
	}
	if count != expectedCount {
		return fmt.Errorf("expected %d matches for arg %s. All args: %s",
			expectedCount, expectedRegex, cmd.args)
	}
	return nil
}

func verifyArgOrder(cmd *command, expectedRegexes ...string) error {
	compiledRegexes := []*regexp.Regexp{}
	for _, regex := range expectedRegexes {
		compiledRegexes = append(compiledRegexes, regexp.MustCompile(matchFullString(regex)))
	}
	expectedArgIndex := 0
	for _, arg := range cmd.args {
		if expectedArgIndex == len(compiledRegexes) {
			break
		} else if compiledRegexes[expectedArgIndex].MatchString(arg) {
			expectedArgIndex++
		}
	}
	if expectedArgIndex != len(expectedRegexes) {
		return fmt.Errorf("expected args %s in order. All args: %s",
			expectedRegexes, cmd.args)
	}
	return nil
}

func verifyEnvUpdate(cmd *command, expectedRegex string) error {
	compiledRegex := regexp.MustCompile(matchFullString(expectedRegex))
	for _, update := range cmd.envUpdates {
		if compiledRegex.MatchString(update) {
			return nil
		}
	}
	return fmt.Errorf("expected at least one match for env update %s. All env updates: %s",
		expectedRegex, cmd.envUpdates)
}

func verifyNoEnvUpdate(cmd *command, expectedRegex string) error {
	compiledRegex := regexp.MustCompile(matchFullString(expectedRegex))
	updates := cmd.envUpdates
	for _, update := range updates {
		if compiledRegex.MatchString(update) {
			return fmt.Errorf("expected no match for env update %s. All env updates: %s",
				expectedRegex, cmd.envUpdates)
		}
	}
	return nil
}

func matchFullString(regex string) string {
	return "^" + regex + "$"
}
