import os
import re
import zipfile
from PIL import Image
import argparse
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

def find_ms_in_filename(filename):
    """从文件名中提取毫秒时间间隔"""
    match = re.search(r'@(\d+)ms', filename)
    if match:
        return int(match.group(1))
    return 40  # 默认值40ms如果找不到匹配

def process_zip_file(zip_path):
    """处理单个ZIP文件，生成GIF"""
    try:
        # 计算对应的GIF路径
        gif_filename = os.path.splitext(os.path.basename(zip_path))[0] + ".gif"
        gif_path = os.path.join(os.path.dirname(zip_path), gif_filename)
        
        # 如果GIF已存在，跳过处理
        if os.path.exists(gif_path):
            return (zip_path, "skip", "对应的GIF已存在")
        
        # 从文件名提取时间间隔
        ms_duration = find_ms_in_filename(os.path.basename(zip_path))
        
        # 创建唯一的临时目录
        with tempfile.TemporaryDirectory(prefix="gif_frames_", dir=os.path.dirname(zip_path)) as temp_dir:
            # 解压ZIP文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # 获取所有JPG文件并按名称排序
            jpg_files = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg')):
                        jpg_files.append(os.path.join(root, file))
            
            if not jpg_files:
                return (zip_path, "warning", "没有找到JPG文件")
            
            # 按文件名排序以确保正确的帧顺序
            jpg_files.sort()
            
            # 打开所有图像
            images = []
            for jpg_file in jpg_files:
                try:
                    with Image.open(jpg_file) as img:
                        images.append(img.copy())
                except Exception as e:
                    return (zip_path, "error", f"无法处理图像 {jpg_file}: {e}")
            
            if not images:
                return (zip_path, "warning", "没有可用的图像")
            
            # 保存为GIF
            images[0].save(
                gif_path,
                save_all=True,
                append_images=images[1:],
                duration=ms_duration,
                loop=0,  # 无限循环
                disposal=2  # 恢复背景
            )
            
            # 释放图像内存
            for img in images:
                img.close()
            
            return (zip_path, "success", gif_path)
        
    except Exception as e:
        return (zip_path, "error", str(e))

def process_folder(folder_path, max_workers=None):
    """遍历文件夹并行处理所有ZIP文件"""
    # 收集所有ZIP文件
    zip_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.zip'):
                zip_path = os.path.join(root, file)
                zip_files.append(zip_path)
    
    if not zip_files:
        print(f"在 {folder_path} 中没有找到任何ZIP文件")
        return
    
    # 使用线程池并行处理
    processed = 0
    skipped = 0
    errors = 0
    
    # 动态调整线程数
    num_files = len(zip_files)
    if max_workers is None:
        # 默认使用CPU核心数，但不超过10个线程
        max_workers = min(os.cpu_count() or 4, 10, num_files)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = {executor.submit(process_zip_file, zip_path): zip_path for zip_path in zip_files}
        
        # 处理结果
        for future in as_completed(futures):
            zip_path = futures[future]
            try:
                result = future.result()
                status = result[1]
                message = result[2]
                
                if status == "success":
                    print(f"✓ 已生成: {message}")
                    processed += 1
                elif status == "skip":
                    skipped += 1
                elif status == "warning":
                    print(f"⚠️ 警告: {zip_path} - {message}")
                elif status == "error":
                    print(f"✗ 处理 {zip_path} 时出错: {message}")
                    errors += 1
            except Exception as e:
                print(f"✗ 处理 {zip_path} 时发生未知错误: {str(e)}")
                errors += 1
    
    # 输出统计信息
    print(f"\n处理完成: 共处理 {len(zip_files)} 个文件")
    print(f"✓ 成功: {processed}")
    print(f"↺ 跳过: {skipped}")
    print(f"✗ 失败: {errors}")

def main():
    parser = argparse.ArgumentParser(description='从ZIP文件并行生成GIF动画')
    parser.add_argument('folder', help='包含ZIP文件的文件夹路径')
    parser.add_argument('--workers', type=int, default=None, 
                        help='最大线程数（默认：自动选择）')
    args = parser.parse_args()
    
    if not os.path.isdir(args.folder):
        print(f"错误: 文件夹 {args.folder} 不存在")
        return
    
    process_folder(args.folder, max_workers=args.workers)

if __name__ == "__main__":
    main()