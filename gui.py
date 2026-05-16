import customtkinter as ctk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import threading
import queue
from pathlib import Path
from archiver import ArchivePacker, ArchiveUnpacker, ArchiveInspector


class ArchiverApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("PYARCH")
        self.geometry("840x620")
        self.resizable(False, False)
        self.queue = queue.Queue()
        self.after(100, self._process_queue)
        self.current_tab = "pack"
        self.task_running = False
        self.sources = []
        self._setup_theme()
        self._build_layout()

    def _setup_theme(self):
        self.font_header = ctk.CTkFont(family="Segoe UI", size=22, weight="bold")
        self.font_body = ctk.CTkFont(family="Segoe UI", size=14)
        self.font_small = ctk.CTkFont(family="Segoe UI", size=12)
        self.font_mono = ctk.CTkFont(family="Consolas", size=11)
        self.bg_main = "#0f1115"
        self.bg_card = "#1a1c23"
        self.bg_input = "#242730"
        self.accent = "#3b82f6"
        self.accent_hover = "#2563eb"
        self.text_primary = "#e5e7eb"
        self.text_secondary = "#9ca3af"
        self.border = "#2a2d37"
        self.success = "#10b981"
        self.error = "#ef4444"

    def _build_layout(self):
        self.configure(fg_color=self.bg_main)

        # Header
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=70)
        self.header.pack(fill="x", padx=24, pady=12)
        ctk.CTkLabel(self.header, text="PYARCH", font=self.font_header, text_color=self.text_primary).pack(side="left")

        # Navigation
        self.nav_frame = ctk.CTkFrame(self, fg_color=self.bg_card, corner_radius=12, height=48)
        self.nav_frame.pack(fill="x", padx=24, pady=(0, 12))
        self.nav_frame.grid_columnconfigure(0, weight=1)
        self.nav_frame.grid_columnconfigure(1, weight=1)
        self.nav_frame.grid_columnconfigure(2, weight=1)
        self.btn_pack = self._nav_btn("Упаковка", "pack")
        self.btn_unpack = self._nav_btn("Распаковка", "unpack")
        self.btn_list = self._nav_btn("Просмотр", "list")
        self.btn_pack.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        self.btn_unpack.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        self.btn_list.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")
        self._update_nav_state()

        # Main Content Card
        self.main_card = ctk.CTkFrame(self, fg_color=self.bg_card, corner_radius=16)
        self.main_card.pack(fill="both", expand=True, padx=24, pady=12)
        self._build_pack_tab()
        self._build_unpack_tab()
        self._build_list_tab()
        self._show_tab("pack")

    def _nav_btn(self, text, tab):
        return ctk.CTkButton(self.nav_frame, text=text, font=self.font_body, corner_radius=10, fg_color=self.bg_input,
                             hover_color=self.accent_hover, text_color=self.text_secondary,
                             command=lambda: self._switch_tab(tab), border_width=1, border_color=self.border)

    def _update_nav_state(self):
        for btn, t in [(self.btn_pack, "pack"), (self.btn_unpack, "unpack"), (self.btn_list, "list")]:
            if t == self.current_tab:
                btn.configure(fg_color=self.accent, text_color="white", border_width=0)
            else:
                btn.configure(fg_color=self.bg_input, text_color=self.text_secondary, border_width=1,
                              border_color=self.border)

    def _switch_tab(self, tab):
        if self.task_running: return
        self.current_tab = tab
        self._update_nav_state()
        self._show_tab(tab)

    def _show_tab(self, tab):
        for w in self.main_card.winfo_children():
            w.pack_forget()
        frames = {"pack": self.tab_pack, "unpack": self.tab_unpack, "list": self.tab_list}
        frames[tab].pack(fill="both", expand=True, padx=32, pady=24)

    def _build_pack_tab(self):
        self.tab_pack = ctk.CTkFrame(self.main_card, fg_color="transparent")

        ctk.CTkLabel(self.tab_pack, text="Источники", font=self.font_body, text_color=self.text_primary).pack(
            anchor="w", pady=(0, 4))
        self.list_box = ctk.CTkTextbox(self.tab_pack, height=140, font=self.font_mono, fg_color=self.bg_input,
                                       corner_radius=10)
        self.list_box.pack(fill="x", pady=(0, 12))
        self.list_box.configure(state="disabled")

        row_btns = ctk.CTkFrame(self.tab_pack, fg_color="transparent")
        row_btns.pack(fill="x", pady=(0, 16))
        ctk.CTkButton(row_btns, text="Папка", fg_color=self.bg_input, hover_color=self.accent_hover,
                      command=self._add_folder).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(row_btns, text="Файлы", fg_color=self.bg_input, hover_color=self.accent_hover,
                      command=self._add_files).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(row_btns, text="Очистить", fg_color=self.bg_input, hover_color=self.error,
                      text_color=self.text_primary, command=self._clear_list).pack(side="left", fill="x", expand=True,
                                                                                   padx=(4, 0))

        ctk.CTkLabel(self.tab_pack, text="Куда сохранить архив", font=self.font_body,
                     text_color=self.text_primary).pack(anchor="w", pady=(0, 4))
        row_dst = ctk.CTkFrame(self.tab_pack, fg_color="transparent")
        row_dst.pack(fill="x", pady=(0, 16))
        self.pack_dst = ctk.CTkEntry(row_dst, height=44, fg_color=self.bg_input, border_color=self.border,
                                     corner_radius=10, font=self.font_body)
        self.pack_dst.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row_dst, text="Обзор...", width=110, height=44, fg_color=self.bg_input,
                      hover_color=self.accent_hover, command=self._select_pack_dst).pack(side="right")

        ctk.CTkLabel(self.tab_pack, text="Уровень сжатия", font=self.font_body, text_color=self.text_primary).pack(
            anchor="w", pady=(0, 4))
        row_lvl = ctk.CTkFrame(self.tab_pack, fg_color="transparent")
        row_lvl.pack(fill="x", pady=(0, 16))
        self.pack_level = ctk.CTkSlider(row_lvl, from_=1, to=9, number_of_steps=8, button_color=self.accent, height=20)
        self.pack_level.set(6)
        self.pack_level.pack(side="left", fill="x", expand=True)
        self.level_label = ctk.CTkLabel(row_lvl, text="6", font=self.font_body, text_color=self.accent, width=24)
        self.level_label.pack(side="left", padx=12)
        self.pack_level.configure(command=lambda v: self.level_label.configure(text=str(int(v))))


        ctk.CTkButton(self.tab_pack, text="Запаковать", height=50, font=self.font_body, corner_radius=12,
                      fg_color=self.accent, hover_color=self.accent_hover, command=self._run_pack).pack(fill="x",
                                                                                                        pady=(8, 16))

        # Прогресс-бар внутри вкладки Упаковки
        ctk.CTkFrame(self.tab_pack, fg_color=self.border, height=2).pack(fill="x", pady=(0, 12))
        self.status_label = ctk.CTkLabel(self.tab_pack, text="Готово", font=self.font_small,
                                         text_color=self.text_secondary)
        self.status_label.pack(anchor="w", pady=(0, 4))
        self.progress = ctk.CTkProgressBar(self.tab_pack, height=8, corner_radius=4, progress_color=self.accent)
        self.progress.pack(fill="x", pady=(0, 6))
        self.progress.set(0)
        self.progress_text = ctk.CTkLabel(self.tab_pack, text="0/0", font=self.font_small, text_color=self.accent)
        self.progress_text.pack(anchor="e")

    def _build_unpack_tab(self):
        self.tab_unpack = ctk.CTkFrame(self.main_card, fg_color="transparent")
        ctk.CTkLabel(self.tab_unpack, text="Архив для распаковки", font=self.font_body,
                     text_color=self.text_primary).pack(anchor="w", pady=(0, 4))
        row_src = ctk.CTkFrame(self.tab_unpack, fg_color="transparent")
        row_src.pack(fill="x", pady=(0, 16))
        self.unpack_src = ctk.CTkEntry(row_src, height=44, fg_color=self.bg_input, border_color=self.border,
                                       corner_radius=10, font=self.font_body)
        self.unpack_src.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row_src, text="Выбрать", width=110, height=44, fg_color=self.bg_input,
                      hover_color=self.accent_hover, command=self._select_unpack_src).pack(side="right")
        ctk.CTkLabel(self.tab_unpack, text="Куда распаковать", font=self.font_body, text_color=self.text_primary).pack(
            anchor="w", pady=(0, 4))
        row_dst = ctk.CTkFrame(self.tab_unpack, fg_color="transparent")
        row_dst.pack(fill="x", pady=(0, 24))
        self.unpack_dst = ctk.CTkEntry(row_dst, height=44, fg_color=self.bg_input, border_color=self.border,
                                       corner_radius=10, font=self.font_body)
        self.unpack_dst.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row_dst, text="Выбрать папку", width=130, height=44, fg_color=self.bg_input,
                      hover_color=self.accent_hover, command=self._select_unpack_dst).pack(side="right")
        ctk.CTkButton(self.tab_unpack, text="Запустить распаковку", height=56, font=self.font_body, corner_radius=14,
                      fg_color=self.accent, hover_color=self.accent_hover, command=self._run_unpack).pack(fill="x",
                                                                                                          pady=(8, 0))

    def _build_list_tab(self):
        self.tab_list = ctk.CTkFrame(self.main_card, fg_color="transparent")
        ctk.CTkLabel(self.tab_list, text="Архив для просмотра", font=self.font_body, text_color=self.text_primary).pack(
            anchor="w", pady=(0, 4))
        row_src = ctk.CTkFrame(self.tab_list, fg_color="transparent")
        row_src.pack(fill="x", pady=(0, 16))
        self.list_src = ctk.CTkEntry(row_src, height=44, fg_color=self.bg_input, border_color=self.border,
                                     corner_radius=10, font=self.font_body)
        self.list_src.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row_src, text="Выбрать", width=110, height=44, fg_color=self.bg_input,
                      hover_color=self.accent_hover, command=self._select_list_src).pack(side="right")
        self.list_frame = ctk.CTkFrame(self.tab_list, fg_color=self.bg_input, corner_radius=10)
        self.list_frame.pack(fill="both", expand=True, pady=(0, 16))
        self.list_content = ctk.CTkTextbox(self.list_frame, font=self.font_mono, fg_color="transparent",
                                           text_color=self.text_primary)
        self.list_content.pack(fill="both", expand=True, padx=8, pady=8)
        self.list_content.configure(state="disabled")
        ctk.CTkButton(self.tab_list, text="Загрузить содержимое", height=50, font=self.font_body, corner_radius=12,
                      fg_color=self.accent, hover_color=self.accent_hover, command=self._run_list).pack(fill="x")

    def _add_folder(self):
        p = filedialog.askdirectory()
        if p and Path(p) not in self.sources:
            self.sources.append(Path(p))
            self._update_sources_ui()

    def _add_files(self):
        paths = filedialog.askopenfilenames()
        for p_str in paths:
            p = Path(p_str)
            if p not in self.sources: self.sources.append(p)
        self._update_sources_ui()

    def _clear_list(self):
        self.sources = []
        self._update_sources_ui()

    def _update_sources_ui(self):
        self.list_box.configure(state="normal")
        self.list_box.delete("1.0", "end")
        for p in self.sources:
            self.list_box.insert("end", f"{p}\n")
        self.list_box.configure(state="disabled")

    def _select_pack_dst(self):
        p = filedialog.asksaveasfilename(defaultextension=".pyarc", filetypes=[("PYARCH", "*.pyarc")])
        if p: self.pack_dst.delete(0, "end"); self.pack_dst.insert(0, p)

    def _select_unpack_src(self):
        p = filedialog.askopenfilename(filetypes=[("PYARCH", "*.pyarc")])
        if p: self.unpack_src.delete(0, "end"); self.unpack_src.insert(0, p)

    def _select_unpack_dst(self):
        p = filedialog.askdirectory()
        if p: self.unpack_dst.delete(0, "end"); self.unpack_dst.insert(0, p)

    def _select_list_src(self):
        p = filedialog.askopenfilename(filetypes=[("PYARCH", "*.pyarc")])
        if p: self.list_src.delete(0, "end"); self.list_src.insert(0, p)

    def _validate_paths(self, mode):
        if mode == "pack":
            if not self.sources:
                return None, None, "Ошибка: Список источников пуст!"
            dst = self.pack_dst.get()
            if not dst:
                return None, None, "Ошибка: Не выбран путь для архива!"

            folder_count = 0
            file_count = 0
            total_size = 0

            for src in self.sources:
                src = src.resolve()
                if src.is_dir():
                    folder_count += 1
                    for f in src.rglob('*'):
                        if f.is_file():
                            file_count += 1
                            total_size += f.stat().st_size
                elif src.is_file():
                    file_count += 1
                    total_size += src.stat().st_size
                else:
                    return None, None, f"Путь не найден: {src}"

            if folder_count > 10:
                return None, None, f"Превышен лимит папок: {folder_count}/10"
            if file_count > 25:
                return None, None, f"Превышен лимит файлов: {file_count}/25"
            if total_size > 1_073_741_824:  # 1 ГБ в байтах
                size_gb = total_size / (1024 ** 3)
                return None, None, f"Превышен лимит размера: {size_gb:.2f} ГБ (макс. 1 ГБ)"

            return self.sources, Path(dst), None

        elif mode == "unpack":
            src, dst = self.unpack_src.get(), self.unpack_dst.get()
            if not src or not dst: return None, None, "Ошибка: Заполните оба поля!"
            if not Path(src).exists(): return None, None, "Ошибка: Архив не найден!"
            return Path(src), Path(dst), None
        else:
            src = self.list_src.get()
            if not src: return None, None, "Ошибка: Укажите архив!"
            if not Path(src).exists(): return None, None, "Ошибка: Архив не найден!"
            return Path(src), None, None

    def _run_pack(self):
        if self.task_running: return
        src, dst, err = self._validate_paths("pack")
        if err: return self._log(err, self.error)
        self.task_running = True
        self.progress.set(0)
        self.progress_text.configure(text="0/0")
        self.status_label.configure(text="Упаковка...", text_color=self.text_secondary)
        threading.Thread(target=self._worker_pack, args=(src, dst, int(self.pack_level.get())), daemon=True).start()

    def _worker_pack(self, sources, output, level):
        try:
            def cb(cur, tot):
                self._queue_update(self._update_progress, cur, tot)

            ArchivePacker(sources, output, level, progress_cb=cb).execute()
            self._queue_update(self._finish_task, "Упаковка завершена успешно!", self.success)
        except Exception as e:
            self._queue_update(self._log, f"Ошибка: {str(e)}", self.error)
            self._queue_update(self._finish_task, "Ошибка при упаковке", self.error)

    def _run_unpack(self):
        if self.task_running: return
        src, dst, err = self._validate_paths("unpack")
        if err: return self._log(err, self.error)
        self.task_running = True
        self.status_label.configure(text="Распаковка...", text_color=self.text_secondary)
        threading.Thread(target=self._worker_unpack, args=(src, dst), daemon=True).start()

    def _worker_unpack(self, archive, dest):
        try:
            def cb(cur, tot):
                self._queue_update(self._update_progress, cur, tot)

            ArchiveUnpacker(archive, dest, progress_cb=cb).execute()
            self._queue_update(self._finish_task, "Распаковка завершена успешно!", self.success)
        except Exception as e:
            self._queue_update(self._log, f"Ошибка: {str(e)}", self.error)
            self._queue_update(self._finish_task, "Ошибка при распаковке", self.error)

    def _run_list(self):
        if self.task_running: return
        src, _, err = self._validate_paths("list")
        if err: return self._log(err, self.error)
        self.task_running = True
        self.status_label.configure(text="Чтение архива...", text_color=self.text_secondary)
        threading.Thread(target=self._worker_list, args=(src,), daemon=True).start()

    def _worker_list(self, archive):
        try:
            import io, sys
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()
            ArchiveInspector(archive).execute()
            sys.stdout = old_stdout
            output = mystdout.getvalue()
            self._queue_update(self._show_list, output)
            self._queue_update(self._finish_task, "Содержимое загружено", self.success)
        except Exception as e:
            self._queue_update(self._log, f"Ошибка: {str(e)}", self.error)
            self._queue_update(self._finish_task, "Ошибка при чтении", self.error)

    def _show_list(self, text):
        self.list_content.configure(state="normal")
        self.list_content.delete("1.0", "end")
        self.list_content.insert("end", text)
        self.list_content.configure(state="disabled")

    def _update_progress(self, current, total):
        self.progress.set(current / total if total > 0 else 0)
        self.progress_text.configure(text=f"{current}/{total}")
        self.status_label.configure(text=f"Обработано: {current}/{total}", text_color=self.text_secondary)

    def _log(self, text, color=None):
        self.status_label.configure(text=text, text_color=color or self.text_secondary)

    def _finish_task(self, msg, color):
        self.task_running = False
        self.progress.set(1.0)
        self.progress_text.configure(text="100%")
        self.status_label.configure(text=msg, text_color=color)
        if color == self.error:
            messagebox.showerror("Ошибка", msg)
        else:
            messagebox.showinfo("Успех", msg)

    def _queue_update(self, func, *args):
        self.queue.put((func, args))

    def _process_queue(self):
        try:
            while True:
                func, args = self.queue.get_nowait()
                func(*args)
        except queue.Empty:
            pass
        self.after(100, self._process_queue)


if __name__ == "__main__":
    app = ArchiverApp()
    app.mainloop()
