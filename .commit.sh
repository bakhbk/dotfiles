#!/bin/bash

commit() {
	echo "🎯 Conventional Commits Generator"
	echo "=================================="

	# Check if in git repository
	if ! git rev-parse --git-dir >/dev/null 2>&1; then
		echo "❌ Not in a git repository"
		return 1
	fi

	# Check if there are staged changes
	if git diff --cached --quiet; then
		echo "❌ No staged changes to commit"
		return 1
	fi

	# ---- New: show number of changed files and line stats ----
	# git diff --cached --shortstat outputs e.g. "110 files changed, 2841 insertions(+), 1389 deletions(-)"
	stats=$(git diff --cached --shortstat)
	if [ -n "$stats" ]; then
		echo "📊 $stats"
	fi
	# ---------------------------------------------------------

	# Commit types
	echo "Select commit type:"
	echo "1) feat: New feature"
	echo "2) fix: Bug fix"
	echo "3) docs: Documentation"
	echo "4) style: Code style"
	echo "5) refactor: Refactoring"
	echo "6) perf: Performance"
	echo "7) test: Tests"
	echo "8) build: Build system"
	echo "9) ci: CI configuration"
	echo "10) chore: Chores"
	echo "11) revert: Revert"
	echo -n "Enter number: "
	read REPLY

	case $REPLY in
	1) type="feat" ;;
	2) type="fix" ;;
	3) type="docs" ;;
	4) type="style" ;;
	5) type="refactor" ;;
	6) type="perf" ;;
	7) type="test" ;;
	8) type="build" ;;
	9) type="ci" ;;
	10) type="chore" ;;
	11) type="revert" ;;
	*)
		echo "Invalid option"
		return 1
		;;
	esac

	echo -n "Enter scope (optional): "
	read scope

	echo -n "Enter description: "
	read description

	if [ -z "$description" ]; then
		echo "❌ Description is required"
		return 1
	fi

	echo -n "Enter body (optional, Ctrl+D to finish): "
	body=$(cat)
	echo

	echo -n "Enter footer (e.g., Closes #123): "
	read footer

	# Build commit message
	if [ -n "$scope" ]; then
		message="$type($scope): $description"
	else
		message="$type: $description"
	fi

	[ -n "$body" ] && message="$message"$'\n\n'"$body"
	[ -n "$footer" ] && message="$message"$'\n\n'"$footer"

	# Add statistics line to message (if available)
	if [ -n "$stats" ]; then
		# Transform: "110 files changed, 2841 insertions(+), 1389 deletions(-)"
		# → "110 files, +2841/-1389 lines"
		stats_line=$(echo "$stats" | awk '{print $1" files, +"$4"/-"$6" lines"}')
		message="$message"$'\n\n'"$stats_line"
	fi

	# Add signoff for preview
	name=$(git config user.name)
	email=$(git config user.email)
	if [ -n "$name" ] && [ -n "$email" ]; then
		message="$message"$'\n\n'"Signed-off-by: $name <$email>"
	fi

	# Create commit (preview)
	echo -e "\n📝 Commit message:"
	echo -e "=================="
	echo -e "$message"
	echo -e "=================="
	# Show stats again for quick reference
	[ -n "$stats" ] && echo -e "\n📊 $stats"

	echo -n "Create commit? [y/N]: "
	read confirm

	if [[ $confirm == [yYдД] ]]; then
		git commit -m "$message"
		echo "✅ Commit created!"
	else
		echo "❌ Commit canceled"
	fi
}
