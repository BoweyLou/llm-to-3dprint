# Target-owned bridge for repo-contract-kit commands.
#
# Keep product-specific targets in this Makefile. The installed kit command
# surface lives in .doc-contract-kit/make/repo-contract.mk and is updated by
# `make kit-update KIT=/path/to/repo-contract-kit`.

include .doc-contract-kit/make/repo-contract.mk
