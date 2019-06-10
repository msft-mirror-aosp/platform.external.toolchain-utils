package main

import (
	"os"
)

type env interface {
	getenv(key string) string
	environ() []string
	getwd() string
}

type processEnv struct {
	wd string
}

func newProcessEnv() (env, error) {
	wd, err := os.Getwd()
	if err != nil {
		return nil, err
	}
	return &processEnv{wd: wd}, nil
}

var _ env = (*processEnv)(nil)

func (env *processEnv) getenv(key string) string {
	return os.Getenv(key)
}

func (env *processEnv) environ() []string {
	return os.Environ()
}

func (env *processEnv) getwd() string {
	return env.wd
}
