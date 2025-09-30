FROM squidfunk/mkdocs-material:latest

# 加入編譯工具（只為了建 wheel）
RUN apk add --no-cache --virtual .build-deps \
      gcc musl-dev linux-headers python3-dev

RUN pip install --no-cache-dir \
    mkdocs-jupyter \
    mkdocs-awesome-pages-plugin \
    mkdocs-exclude \
    mkdocs-minify-plugin \
    mkdocs-git-revision-date-localized-plugin \
    mdx_truly_sane_lists \
    openai \
    jieba
    
# 裝完移除編譯工具，縮小體積
RUN apk del .build-deps

WORKDIR /docs
