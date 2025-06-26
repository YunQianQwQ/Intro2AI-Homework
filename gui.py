import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os
import threading
import sys

class PDFSummarizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF 摘要生成工具")
        self.root.geometry("600x500")
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # PDF文件选择
        ttk.Label(self.main_frame, text="PDF文件路径:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.pdf_path_entry = ttk.Entry(self.main_frame, width=50)
        self.pdf_path_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Button(self.main_frame, text="浏览...", command=self.browse_pdf).grid(row=0, column=2, sticky=tk.W, pady=5)
        
        # API密钥
        ttk.Label(self.main_frame, text="DeepSeek API密钥:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_entry = ttk.Entry(self.main_frame, width=50, show="*")
        self.api_key_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # 输出目录
        ttk.Label(self.main_frame, text="输出目录:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.output_dir_entry = ttk.Entry(self.main_frame, width=50)
        self.output_dir_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
        self.output_dir_entry.insert(0, "output")
        ttk.Button(self.main_frame, text="浏览...", command=self.browse_output_dir).grid(row=2, column=2, sticky=tk.W, pady=5)
        
        # 参数设置
        ttk.Label(self.main_frame, text="摘要参数设置", font=('Arial', 10, 'bold')).grid(row=3, column=0, columnspan=3, pady=10, sticky=tk.W)
        
        # 最大token数
        ttk.Label(self.main_frame, text="最大Token数 (建议3000):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.max_token_spin = ttk.Spinbox(self.main_frame, from_=1000, to=10000, increment=500)
        self.max_token_spin.grid(row=4, column=1, sticky=tk.W, pady=5)
        self.max_token_spin.set("3000")
        
        # 生成迭代次数
        ttk.Label(self.main_frame, text="生成迭代次数 (建议2):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.gen_iter_spin = ttk.Spinbox(self.main_frame, from_=1, to=5)
        self.gen_iter_spin.grid(row=5, column=1, sticky=tk.W, pady=5)
        self.gen_iter_spin.set("2")
        
        # 验证迭代次数
        ttk.Label(self.main_frame, text="验证迭代次数 (建议2):").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.val_iter_spin = ttk.Spinbox(self.main_frame, from_=1, to=5)
        self.val_iter_spin.grid(row=6, column=1, sticky=tk.W, pady=5)
        self.val_iter_spin.set("2")
        
        # 验证题目数量
        ttk.Label(self.main_frame, text="验证题目数量 (建议20-50):").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.val_problems_spin = ttk.Spinbox(self.main_frame, from_=5, to=100)
        self.val_problems_spin.grid(row=7, column=1, sticky=tk.W, pady=5)
        self.val_problems_spin.set("20")
        
        # 最大等待时间
        ttk.Label(self.main_frame, text="最大等待时间(秒):").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.max_wait_spin = ttk.Spinbox(self.main_frame, from_=30, to=600)
        self.max_wait_spin.grid(row=8, column=1, sticky=tk.W, pady=5)
        self.max_wait_spin.set("300")
        
        # 进度条
        self.progress = ttk.Progressbar(self.main_frame, orient="horizontal", length=400, mode="determinate")
        self.progress.grid(row=9, column=0, columnspan=3, pady=20)
        
        # 状态标签
        self.status_label = ttk.Label(self.main_frame, text="准备就绪", foreground="blue")
        self.status_label.grid(row=10, column=0, columnspan=3, pady=5)
        
        # 按钮框架
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=11, column=0, columnspan=3, pady=10)
        
        # 开始按钮
        self.start_button = ttk.Button(self.button_frame, text="开始处理", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        # 取消按钮
        self.cancel_button = ttk.Button(self.button_frame, text="取消", command=self.cancel_processing, state=tk.DISABLED)
        # self.cancel_button.pack(side=tk.LEFT, padx=5)
        
        # 退出按钮
        self.quit_button = ttk.Button(self.button_frame, text="退出", command=root.quit)
        self.quit_button.pack(side=tk.RIGHT, padx=5)
        
        # 处理标志
        self.processing = False
        self.cancel_flag = False
        
    def browse_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF文件", "*.pdf")])
        if file_path:
            self.pdf_path_entry.delete(0, tk.END)
            self.pdf_path_entry.insert(0, file_path)
    
    def browse_output_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, dir_path)
    
    def update_status(self, message, color="blue"):
        self.status_label.config(text=message, foreground=color)
        self.root.update()
    
    def start_processing(self):
        pdf_path = self.pdf_path_entry.get()
        api_key = self.api_key_entry.get()
        output_dir = self.output_dir_entry.get()
        
        if not pdf_path:
            messagebox.showerror("错误", "请选择PDF文件")
            return
        
        if not api_key:
            messagebox.showerror("错误", "请输入API密钥")
            return
        
        if not os.path.exists(pdf_path):
            messagebox.showerror("错误", "PDF文件不存在")
            return
        
        try:
            max_token = int(self.max_token_spin.get())
            gen_iter = int(self.gen_iter_spin.get())
            val_iter = int(self.val_iter_spin.get())
            val_problems = int(self.val_problems_spin.get())
            max_wait = int(self.max_wait_spin.get())
        except ValueError:
            messagebox.showerror("错误", "参数必须是整数")
            return
        
        self.processing = True
        self.cancel_flag = False
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        
        # 创建并启动处理线程
        processing_thread = threading.Thread(
            target=self.run_processing,
            args=(pdf_path, api_key, output_dir, max_token, gen_iter, val_iter, val_problems, max_wait),
            daemon=True
        )
        processing_thread.start()
        
        # 启动进度条更新
        self.update_progress()
    
    def cancel_processing(self):
        self.cancel_flag = True
        self.update_status("正在取消...", "orange")
        self.cancel_button.config(state=tk.DISABLED)
    
    def update_progress(self):
        if self.processing:
            current_value = self.progress["value"]
            if current_value < 100:
                self.progress["value"] = current_value + 1
            else:
                self.progress["value"] = 0
            self.root.after(100, self.update_progress)
    
    def run_processing(self, pdf_path, api_key, output_dir, max_token, gen_iter, val_iter, val_problems, max_wait):
        try:
            # 第一步：使用fix.py处理PDF
            self.update_status("正在转换PDF为文本...")
            fix_cmd = [
                sys.executable, "fix.py",
                pdf_path,
                "--api_key", api_key,
                "--output_dir", output_dir
            ]
            
            self.progress["value"] = 10
            result = subprocess.run(fix_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.update_status(f"PDF转换失败: {result.stderr}", "red")
                self.processing = False
                self.root.after(0, self.reset_buttons)
                return
            
            # 获取生成的input.txt路径
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            input_txt = os.path.join(output_dir, f"{base_name}_input.txt")
            
            if not os.path.exists(input_txt):
                self.update_status("无法找到生成的input.txt文件", "red")
                self.processing = False
                self.root.after(0, self.reset_buttons)
                return
            
            self.progress["value"] = 30
            self.update_status("PDF转换完成，正在生成摘要...")
            
            # 第二步：使用gen.py生成摘要
            gen_cmd = [
                sys.executable, "gen.py",
                "--filename", input_txt,
                "--maxtoken", str(max_token),
                "--apikey", api_key,
                "--output_dir", output_dir,
                "--geniter", str(gen_iter),
                "--valiter", str(val_iter),
                "--valproblems", str(val_problems),
                "--maxwait", str(max_wait)
            ]
            
            result = subprocess.run(gen_cmd, capture_output=True, text=True)
            self.progress["value"] = 90
            
            if result.returncode != 0:
                self.update_status(f"摘要生成失败: {result.stderr}", "red")
            else:
                self.update_status("处理完成！", "green")
                self.progress["value"] = 100
                
                # 显示结果路径
                final_summary = os.path.join(output_dir, "final_summary.txt")
                messagebox.showinfo("完成", f"处理完成！最终摘要已保存到:\n{final_summary}")
            
        except Exception as e:
            self.update_status(f"处理出错: {str(e)}", "red")
        finally:
            self.processing = False
            self.root.after(0, self.reset_buttons)
    
    def reset_buttons(self):
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        if not self.processing:
            self.progress["value"] = 0

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFSummarizerApp(root)
    root.mainloop()