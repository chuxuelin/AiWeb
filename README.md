# MoveWell

Flask + MySQL 运动健康社区应用。

## 本地启动

1. 安装依赖：

   ```powershell
   pip install -r requirements.txt
   ```

2. 配置数据库环境变量（也可使用 `db.py` 中的本地默认值）：

   ```powershell
   $env:MYSQL_HOST = "127.0.0.1"
   $env:MYSQL_PORT = "3306"
   $env:MYSQL_USER = "root"
   $env:MYSQL_PASSWORD = "你的数据库密码"
   $env:MYSQL_DATABASE = "health_app"
   ```

3. 初始化数据库和测试数据：

   ```powershell
   python init_db.py
   ```

4. 启动开发服务器：

   ```powershell
   python app.py
   ```

默认测试账号：`admin` / `123`。

## 目录说明

- `app.py`：Flask 页面路由和 API
- `db.py`：MySQL 连接与查询封装
- `init_db.py`：数据库初始化和兼容性迁移
- `schema.sql`：数据库结构基线
- `templates/`：Jinja/Vue 页面模板
- `static/`：前端脚本、样式和本地第三方资源
- `requirements.txt`：Python 依赖

项目已移除 Railway 和 GitHub Pages 部署配置。`gunicorn` 依赖仍保留，可用于其他支持 WSGI 的部署平台。
