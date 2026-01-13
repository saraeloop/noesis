.PHONY: build run clean tidy

# Binary name
BINARY := noesis-tui

# Build the TUI
build:
	go build -o $(BINARY) .

# Run the TUI
run: build
	./$(BINARY)

# Download dependencies
tidy:
	go mod tidy

# Clean build artifacts
clean:
	rm -f $(BINARY)

# Development: build and run
dev: build
	./$(BINARY)

# Install to $GOPATH/bin
install:
	go install .
