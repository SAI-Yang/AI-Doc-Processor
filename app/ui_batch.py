"""批量处理控制 - 后台线程 + 进度跟踪 + 日志输出"""

import asyncio
import time
import traceback
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QListWidget, QListWidgetItem,
    QFrame, QMessageBox, QSizePolicy, QProgressBar,
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QMutex, QMutexLocker
from PyQt5.QtGui import QColor, QFont, QTextCursor

from app import (
    FILE_PENDING, FILE_PROCESSING, FILE_DONE, FILE_FAILED,
    STATUS_SYMBOLS, STATUS_COLORS, STATUS_TEXTS,
)
from app.config import AppConfig
from app.document import read_document, write_document
from app.llm_client import create_client
from app.template_manager import TemplateManager


class BatchWorker(QThread):
    """批量处理工作线程"""

    # 进度信号
    progress_range = pyqtSignal(int)          # 设置总进度
    progress_update = pyqtSignal(int)         # 更新进度
    file_status_changed = pyqtSignal(int, str)  # 文件索引, 状态标识 (pending/processing/done/failed)

    # 文件级信号
    file_started = pyqtSignal(int, str)       # 索引, 文件名
    file_finished = pyqtSignal(int, str, bool)  # 索引, 文件名, 成功
    file_content_result = pyqtSignal(int, str, str)  # 索引, 原文, 处理结果

    # 日志信号
    log = pyqtSignal(str)                     # 日志消息
    log_error = pyqtSignal(str)               # 错误日志

    # 完成信号
    all_finished = pyqtSignal(dict)           # 汇总数据

    def __init__(self, file_paths: list[Path], template_pipeline: list[tuple],
                 config: AppConfig, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.template_pipeline = template_pipeline  # [(template_id, template_data), ...]
        self.config = config
        self._mutex = QMutex()
        self._paused = False
        self._cancelled = False
        self._current_index = 0

    def pause(self):
        with QMutexLocker(self._mutex):
            self._paused = True

    def resume(self):
        with QMutexLocker(self._mutex):
            self._paused = False

    def cancel(self):
        with QMutexLocker(self._mutex):
            self._cancelled = True

    def is_paused(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._paused

    def run(self):
        """线程主循环"""
        total = len(self.file_paths)
        success_count = 0
        fail_count = 0
        start_time = time.time()
        output_dir = Path.home() / '.ai-doc-processor' / 'output'
        output_dir.mkdir(parents=True, exist_ok=True)

        self.progress_range.emit(total)
        self.log.emit(f'开始批量处理，共 {total} 个文件')
        self.log.emit(f'模板流水线: {len(self.template_pipeline)} 步')
        for i, (tid, _) in enumerate(self.template_pipeline):
            self.log.emit(f'  步骤 {i+1}: {tid}')

        # 生成输出子目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_dir = output_dir / f'batch_{timestamp}'
        session_dir.mkdir(parents=True, exist_ok=True)

        try:
            template_mgr = TemplateManager()
            llm_config = self.config.llm

            for idx, file_path in enumerate(self.file_paths):
                # 检查取消
                with QMutexLocker(self._mutex):
                    if self._cancelled:
                        self.log.emit('用户取消处理')
                        break

                # 暂停检查
                while self.is_paused():
                    if self._cancelled:
                        break
                    self.msleep(200)

                if self._cancelled:
                    break

                self._current_index = idx
                file_name = file_path.name
                self.file_started.emit(idx, file_name)
                self.file_status_changed.emit(idx, 'processing')
                self.log.emit(f'[{idx+1}/{total}] 处理: {file_name}')

                try:
                    # 1. 读取文档
                    self.log.emit(f'  读取文件...')
                    doc = read_document(file_path)
                    content = doc.content
                    original_content = content

                    if not content.strip():
                        self.log_error.emit(f'  文件内容为空: {file_name}')
                        self.file_status_changed.emit(idx, 'failed')
                        self.file_finished.emit(idx, file_name, False)
                        fail_count += 1
                        self.progress_update.emit(idx + 1)
                        continue

                    # 2. 逐步骤处理
                    current_content = content
                    for step_idx, (tid, tdata) in enumerate(self.template_pipeline):
                        self.log.emit(f'  执行步骤 {step_idx+1}: {tid}')

                        tpl = template_mgr.get(tid)
                        if tpl:
                            system_prompt = tpl.system_prompt
                            user_prompt = tpl.user_prompt.replace('{content}', current_content)
                            if '{text}' in user_prompt:
                                user_prompt = user_prompt.replace('{text}', current_content)
                        else:
                            # 自定义模板
                            system_prompt = tdata.get('system_prompt', '')
                            user_prompt = tdata.get('user_prompt', '').replace('{text}', current_content)
                            user_prompt = user_prompt.replace('{content}', current_content)

                        # 临时覆盖温度/max_tokens
                        llm_config.temperature = tdata.get('temperature', llm_config.temperature)
                        llm_config.max_tokens = tdata.get('max_tokens', llm_config.max_tokens)

                        # 3. 调用 API
                        client = create_client(llm_config)
                        self.log.emit(f'  调用 API ({llm_config.model})...')

                        # 使用 asyncio.run 同步调用异步客户端
                        processed = asyncio.run(
                            client.process_content(
                                content=current_content,
                                system_prompt=system_prompt,
                                user_prompt=user_prompt,
                            )
                        )

                        current_content = processed.strip() or current_content

                    # 4. 写入结果
                    result_content = current_content
                    output_path = session_dir / f'{file_path.stem}_processed{file_path.suffix}'
                    self.log.emit(f'  写入结果: {output_path.name}')

                    # 简单写入文本
                    output_path.write_text(result_content, encoding='utf-8')

                    # 5. 发送结果信号
                    self.file_content_result.emit(idx, original_content, result_content)

                    self.file_status_changed.emit(idx, 'done')
                    self.file_finished.emit(idx, file_name, True)
                    success_count += 1
                    self.log.emit(f'  ✓ 完成: {file_name}')

                except ImportError as e:
                    self.log_error.emit(f'  缺少依赖: {e}')
                    self.file_status_changed.emit(idx, 'failed')
                    self.file_finished.emit(idx, file_name, False)
                    fail_count += 1

                except Exception as e:
                    self.log_error.emit(f'  ✗ 失败: {file_name} - {e}')
                    tb = traceback.format_exc()
                    self.log_error.emit(f'    详细: {tb[:200]}')
                    self.file_status_changed.emit(idx, 'failed')
                    self.file_finished.emit(idx, file_name, False)
                    fail_count += 1

                finally:
                    self.progress_update.emit(idx + 1)

        except Exception as e:
            self.log_error.emit(f'处理过程异常: {e}')
            self.log_error.emit(traceback.format_exc()[:500])

        total_time = time.time() - start_time
        summary = {
            'total': total,
            'success': success_count,
            'fail': fail_count,
            'duration': total_time,
            'output_dir': str(session_dir),
            'template_pipeline': [t[0] for t in self.template_pipeline],
        }

        self.log.emit('─' * 40)
        self.log.emit(f'处理完成! 成功: {success_count}, 失败: {fail_count}, 耗时: {total_time:.1f}秒')
        self.all_finished.emit(summary)


class BatchControlWidget(QWidget):
    """批量处理控制面板"""

    file_content_ready = pyqtSignal(int, str, str)  # index, original, processed
    file_done = pyqtSignal(int, str, bool)           # index, name, success

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: BatchWorker = None
        self._file_paths: list[Path] = []
        self._file_status: dict[int, str] = {}  # idx -> status
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.start_btn = QPushButton('▶ 开始处理')
        self.start_btn.setToolTip('开始批量处理 (F5)')
        self.start_btn.setStyleSheet(
            'QPushButton { background-color: #238636; border-color: #2ea043; }'
            'QPushButton:hover { background-color: #2ea043; }'
        )
        self.start_btn.clicked.connect(self._start)
        btn_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton('⏸ 暂停')
        self.pause_btn.setToolTip('暂停/继续处理 (Ctrl+P)')
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._toggle_pause)
        btn_layout.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton('⏹ 取消')
        self.cancel_btn.setToolTip('取消当前处理 (Escape)')
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        btn_layout.addWidget(self.cancel_btn)

        # 进度信息
        btn_layout.addStretch()
        self.progress_label = QLabel('就绪')
        self.progress_label.setStyleSheet('color: #8b949e; font-size: 12px;')
        btn_layout.addWidget(self.progress_label)

        layout.addLayout(btn_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # 文件处理状态列表
        self.status_list = QListWidget()
        self.status_list.setMaximumHeight(120)
        self.status_list.setAlternatingRowColors(False)
        layout.addWidget(self.status_list)

    # ── 控制接口 ────────────────────────────────────────

    def set_files(self, paths: list[Path]):
        """设置待处理文件"""
        self._file_paths = list(paths)
        self._update_status_list()

    def start_batch(self, paths: list[Path], template_pipeline: list[tuple],
                    config: AppConfig):
        """开始批量处理"""
        self._file_paths = list(paths)
        self._template_pipeline = template_pipeline
        self._config = config
        self._start()

    def _start(self):
        if not self._file_paths:
            self.progress_label.setText('没有待处理的文件')
            return

        if not self._template_pipeline:
            self.progress_label.setText('请选择处理模板')
            return

        if self._worker and self._worker.isRunning():
            return

        # 检查 API 配置
        if not self._config.llm.api_key:
            QMessageBox.warning(self, '提示', '请先在设置中配置 API Key')
            return

        # 创建并启动工作线程
        self._worker = BatchWorker(
            self._file_paths, self._template_pipeline, self._config
        )

        # 连接信号
        self._worker.progress_range.connect(self.progress_bar.setMaximum)
        self._worker.progress_update.connect(self.progress_bar.setValue)
        self._worker.file_status_changed.connect(self._on_file_status)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_finished.connect(self._on_file_finished)
        self._worker.file_content_result.connect(self.file_content_ready.emit)
        self._worker.file_finished.connect(self.file_done.emit)
        self._worker.log.connect(self._on_log)
        self._worker.log_error.connect(self._on_log_error)
        self._worker.all_finished.connect(self._on_all_finished)

        self._worker.finished.connect(self._on_worker_finished)

        # 更新 UI 状态
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.pause_btn.setText('⏸ 暂停')
        self.progress_label.setText('处理中...')

        self._file_status.clear()
        self._update_status_list()

        self._worker.start()

    def _toggle_pause(self):
        if not self._worker:
            return
        if self._worker.is_paused():
            self._worker.resume()
            self.pause_btn.setText('⏸ 暂停')
            self.progress_label.setText('处理中...')
        else:
            self._worker.pause()
            self.pause_btn.setText('▶ 继续')
            self.progress_label.setText('已暂停')

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
            self.progress_label.setText('正在取消...')
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)

    # ── 信号响应 ────────────────────────────────────────

    def _on_file_status(self, idx: int, status: str):
        self._file_status[idx] = status
        self._update_status_list()

    def _on_file_started(self, idx: int, name: str):
        pass

    def _on_file_finished(self, idx: int, name: str, success: bool):
        pass

    def _on_log(self, msg: str):
        pass  # 由外部日志组件处理

    def _on_log_error(self, msg: str):
        pass

    def _on_all_finished(self, summary: dict):
        self.progress_label.setText(f"完成! 成功: {summary['success']}, 失败: {summary['fail']}")
        all_finished = summary  # 留给外部处理

    def _on_worker_finished(self):
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.pause_btn.setText('⏸ 暂停')
        self._worker = None

    # ── 状态列表 ────────────────────────────────────────

    def _update_status_list(self):
        self.status_list.clear()
        for idx, path in enumerate(self._file_paths):
            status = self._file_status.get(idx, 'pending')
            symbol = {'pending': '○', 'processing': '●', 'done': '✓', 'failed': '✗'}.get(status, '○')
            item = QListWidgetItem(f'  {symbol}  {path.name}')
            item.setToolTip(str(path))

            color = {
                'pending': '#8b949e', 'processing': '#58a6ff',
                'done': '#3fb950', 'failed': '#f85149',
            }.get(status, '#8b949e')
            item.setForeground(QColor(color))

            self.status_list.addItem(item)

        # 滚动到底部
        self.status_list.scrollToBottom()


class LogWidget(QTextEdit):
    """日志输出组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont('Consolas', 11))
        self.setPlaceholderText('处理日志将在此显示')

    def log_info(self, msg: str):
        """添加信息日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        html = f'<span style="color:#8b949e;">[{timestamp}]</span> {self._escape(msg)}<br>'
        self._append_html(html)

    def log_error(self, msg: str):
        """添加错误日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        html = f'<span style="color:#8b949e;">[{timestamp}]</span> <span style="color:#f85149;">{self._escape(msg)}</span><br>'
        self._append_html(html)

    def log_success(self, msg: str):
        """添加成功日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        html = f'<span style="color:#8b949e;">[{timestamp}]</span> <span style="color:#3fb950;">{self._escape(msg)}</span><br>'
        self._append_html(html)

    def _append_html(self, html: str):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def clear_log(self):
        self.clear()
