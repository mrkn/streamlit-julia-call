# streamlit-julia-call

## Description

This is an extension to Streamlit that enables calling Julia from Streamlit applications.

## Demo application

The simple demo application is available in the [streamlit-julia-call-demo](https://github.com/mrkn/streamlit-julia-call-demo) repository.

## Installation

Currently, this hasn't been published to any public package repositories.
To install, add this repository's URL to your preferred package management system, such as poetry.

If you use poetry it's done by following command:

```
$ poetry add git+https://github.com/mrkn/streamlit-julia-call.git
```

## Development

### Running tests with playwright

First, you need to install playwright before running tests.  To prepare playwright, execute the following command.

```
$ poetry run python -m playwright install --with-deps
```

You can run all the tests that use playwright by the command below.

```
$ make tests-playwright
```

## Project status

This project is currently a work in progress and in the proof-of-concept stage.

### Known Issues

There are the following limitations in the current version v0.1.0.

- Multiple sessions are not yet supported. You can easily create race conditions in Julia code embedded in page scripts by simultaneous access from multiple clients.
- Julia code doesn't run concurrently because pyjulia doesn't release the GIL during the execution of Julia code.
- On macOS, processes cannot be successfully terminated by either SIGINT or SIGTERM signal.

### Development milestones

We have outlined several key milestones for future versions

#### v0.2.0 (WIP)

In the development of the version v0.2.0, we're focusing to support multiple sessions.

#### v0.3.0

In the version v0.3.0, we want to add juliacall support.

#### v0.4.0

We want to add a feature for initializing Julia runtime environment in v0.4.0. This should be useful to make the first page view faster by precompiling functions.

#### v0.5.0

In v0.5.0 we want to realize the parallel execution of Julia code when `JULIA_NUM_THREADS` > 1.

#### v1.0.0

We want to support calling Streamlit's functions such as `st.write` from Julia code, and then release v1.0.0.

## Author

Kenta Murata

## License

Copyright &copy; 2024 Kenta Murata.
This project is [MIT](LICENSE.txt) licensed.
