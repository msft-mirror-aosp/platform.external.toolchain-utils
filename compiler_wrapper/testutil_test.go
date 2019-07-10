package main

import (
	"bytes"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"os/exec"
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
	t            *testing.T
	tempDir      string
	env          []string
	cfg          *config
	inputCmd     *command
	lastCmd      *command
	cmdCount     int
	cmdMock      func(cmd *command, stdout io.Writer, stderr io.Writer) error
	stdoutBuffer bytes.Buffer
	stderrBuffer bytes.Buffer
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
		cfg:     &config{},
	}
	// Note: It's ok to use the hardened wrapper here, as we replace its config
	// on each run.
	ctx.updateConfig(oldHardenedWrapperPathForTest, &config{})

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

func (ctx *testContext) stdout() io.Writer {
	return &ctx.stdoutBuffer
}

func (ctx *testContext) stdoutString() string {
	return ctx.stdoutBuffer.String()
}

func (ctx *testContext) stderr() io.Writer {
	return &ctx.stderrBuffer
}

func (ctx *testContext) stderrString() string {
	return ctx.stderrBuffer.String()
}

func (ctx *testContext) run(cmd *command, stdout io.Writer, stderr io.Writer) error {
	// Keep calling the old wrapper when we are comparing the output of the
	// old wrapper to the new wrapper.
	if isCompareToOldWrapperCmd(cmd) {
		execCmd := newExecCmd(ctx, cmd)
		execCmd.Stdout = stdout
		execCmd.Stderr = stderr
		return execCmd.Run()
	}
	ctx.cmdCount++
	ctx.lastCmd = cmd
	if ctx.cmdMock != nil {
		return ctx.cmdMock(cmd, stdout, stderr)
	}
	return nil
}

func (ctx *testContext) exec(cmd *command) error {
	ctx.cmdCount++
	ctx.lastCmd = cmd
	if ctx.cmdMock != nil {
		return ctx.cmdMock(cmd, ctx.stdout(), ctx.stderr())
	}
	return nil
}

func (ctx *testContext) must(exitCode int) *command {
	if exitCode != 0 {
		ctx.t.Fatalf("expected no error, but got %d. Stderr: %s",
			exitCode, ctx.stderrString())
	}
	return ctx.lastCmd
}

func (ctx *testContext) mustFail(exitCode int) string {
	if exitCode == 0 {
		ctx.t.Fatalf("expected an error, but got none")
	}
	return ctx.stderrString()
}

func (ctx *testContext) updateConfig(wrapperChrootPath string, cfg *config) {
	*ctx.cfg = *cfg
	ctx.cfg.overwriteOldWrapperCfg = true
	ctx.cfg.mockOldWrapperCmds = true
	if *crosRootDirFlag != "" {
		ctx.cfg.oldWrapperPath = filepath.Join(*crosRootDirFlag, wrapperChrootPath)
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

func verifyInternalError(stderr string) error {
	if !strings.Contains(stderr, "Internal error") {
		return fmt.Errorf("expected an internal error. Got: %s", stderr)
	}
	if ok, _ := regexp.MatchString(`\w+.go:\d+`, stderr); !ok {
		return fmt.Errorf("expected a source line reference. Got: %s", stderr)
	}
	return nil
}

func verifyNonInternalError(stderr string, expectedRegex string) error {
	if strings.Contains(stderr, "Internal error") {
		return fmt.Errorf("expected a non internal error. Got: %s", stderr)
	}
	if ok, _ := regexp.MatchString(`\w+.go:\d+`, stderr); ok {
		return fmt.Errorf("expected no source line reference. Got: %s", stderr)
	}
	if ok, _ := regexp.MatchString(matchFullString(expectedRegex), strings.TrimSpace(stderr)); !ok {
		return fmt.Errorf("expected stderr matching %s. Got: %s", expectedRegex, stderr)
	}
	return nil
}

func matchFullString(regex string) string {
	return "^" + regex + "$"
}

func newExitCodeError(exitCode int) error {
	// It's actually hard to create an error that represents a command
	// with exit code. Using a real command instead.
	tmpCmd := exec.Command("/usr/bin/sh", "-c", fmt.Sprintf("exit %d", exitCode))
	return tmpCmd.Run()
}

func isForwardToOldWrapperCmd(cmd *command) bool {
	for _, arg := range cmd.args {
		if strings.Contains(arg, forwardToOldWrapperFilePattern) {
			return true
		}
	}
	return false
}

func isCompareToOldWrapperCmd(cmd *command) bool {
	for _, arg := range cmd.args {
		if strings.Contains(arg, compareToOldWrapperFilePattern) {
			return true
		}
	}
	return false
}