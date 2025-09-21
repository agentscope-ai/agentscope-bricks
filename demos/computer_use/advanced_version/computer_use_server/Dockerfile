# 使用基础镜像
FROM modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/python:3.10

# 配置 pip 使用国内镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# 切换到root用户执行需要权限的操作
USER root

# 更新包索引并安装 Nginx 和其他必要工具
RUN apt-get update && \
    apt-get install -y nginx sudo && \
    rm -rf /var/lib/apt/lists/*

# 创建用户并配置sudo权限
RUN useradd -m -u 1000 user && \
    echo "user ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY --chown=user ./requirements.txt requirements.txt

# 安装依赖
RUN pip install --no-cache-dir --upgrade pip
RUN for i in {1..10}; do pip install --no-cache-dir --upgrade -r requirements.txt && break || sleep 5; done
RUN pip install --no-cache-dir spy-agent-build-sdk==0.0.29

# 复制应用程序代码
COPY --chown=user . /app

# 复制 Nginx 配置文件
COPY nginx.conf /etc/nginx/nginx.conf

# 确保 start.sh 具有可执行权限
RUN chmod +x /app/start.sh

# 暴露端口
EXPOSE 7860

# 启动服务
CMD ["/bin/bash", "/app/start.sh"]
