from pathlib import Path

# 配置工作目录（根据你的项目修改）
WORKDIR = Path.cwd()  # 或者设置为你的项目根目录


def safe_path(path_str: str) -> Path:
    """
    安全检查：确保路径不会逃逸出工作目录
    防止路径遍历攻击（如 ../../../etc/passwd）
    """
    path = (WORKDIR / path_str).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {path_str}")
    return path


def read_file(path: str, limit: int | None = None) -> str:
    """
    读取文件内容

    Args:
        path: 相对于工作目录的文件路径
        limit: 可选，限制读取的行数（用于读取大文件的前 N 行）

    Returns:
        文件内容字符串（最多 50000 字符）
    """
    try:
        file_path = safe_path(path)
        lines = file_path.read_text().splitlines()

        # 如果设置了行数限制，添加截断提示
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]

        return "\n".join(lines)[:50000]
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as exc:
        return f"Error: {exc}"

