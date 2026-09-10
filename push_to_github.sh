#!/bin/bash

# Script tự động đẩy code Gmail Intelligence System lên GitHub

echo "============================================="
echo "🚀 Pre-flight check: Protecting Secrets"
echo "============================================="

# Kiểm tra file .gitignore
if [ ! -f .gitignore ]; then
    echo "Creating .gitignore..."
    echo ".env" > .gitignore
    echo "credentials.json" >> .gitignore
    echo "token.json" >> .gitignore
    echo "*.db" >> .gitignore
    echo "__pycache__/" >> .gitignore
    echo ".pytest_cache/" >> .gitignore
fi

# Khởi tạo git nếu chưa có
if [ ! -d .git ]; then
    echo "📦 Initializing local Git repository..."
    git init
    git branch -M main
fi

# Hỏi người dùng URL của GitHub repository nếu chưa set origin
REMOTE_URL=$(git remote get-url origin 2>/dev/null)

if [ -z "$REMOTE_URL" ]; then
    echo "📌 Chưa cấu hình GitHub Repository Remote."
    read -p "Nhập URL GitHub Repository của bạn (ví dụ: https://github.com/username/gmail-optimizer.git): " REPO_URL
    if [ -n "$REPO_URL" ]; then
        git remote add origin "$REPO_URL"
    else
        echo "❌ Chưa nhập URL repository. Dừng quá trình."
        exit 1
    fi
else
    echo "🔗 GitHub Remote URL hiện tại: $REMOTE_URL"
fi

# Nhập commit message
read -p "Nhập thông điệp Commit (bấm Enter để dùng mặc định: 'Initial commit'): " COMMIT_MSG
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="Initial commit: Gmail Intelligence System"
fi

echo "➕ Staging files..."
git add .

echo "📝 Committing changes..."
git commit -m "$COMMIT_MSG"

echo "⬆️ Pushing to GitHub (branch: main)..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo "============================================="
    echo "✅ Đã đẩy code thành công lên GitHub!"
    echo "============================================="
else
    echo "============================================="
    echo "⚠️ Đẩy code thất bại. Hãy kiểm tra lại URL repo hoặc quyền truy cập GitHub."
    echo "============================================="
fi
