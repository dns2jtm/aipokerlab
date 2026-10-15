"""Small, always-on-top guidance panel sharing the main app's live state."""
import tkinter as tk
from tkinter import ttk


class CompactGuidance:
    def __init__(self, app):
        self.app = app
        self.on_minimise = tk.BooleanVar(app.root, value=bool(getattr(app, '_minimize_to_tray', False)))
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title('RTA · Compact guidance')
        self.window.configure(bg=app.BG, padx=14, pady=12)
        self.window.attributes('-topmost', True)
        self.window.resizable(False, False)
        self.window.minsize(360, 1)
        self.window.protocol('WM_DELETE_WINDOW', self.restore)
        self.window.bind('<Escape>', lambda _: self.restore())
        shortcut = '<Command-Shift-M>' if app.root.tk.call('tk', 'windowingsystem') == 'aqua' else '<Control-Shift-M>'
        app.root.bind(shortcut, lambda _: self.show())
        self.window.bind(shortcut, lambda _: self.restore())
        self.placed = False
        header = tk.Frame(self.window, bg=app.BG)
        header.pack(fill='x')
        tk.Label(header, text='RTA', bg=app.BG, fg=app.FG,
                 font=('Helvetica',12,'bold')).pack(side='left')
        ttk.Button(header, text='Expand', command=self.restore).pack(side='right')
        modes = tk.Frame(self.window, bg=app.BG)
        modes.pack(fill='x', pady=8)
        for title,mode in [('Preflop','preflop'),('Postflop','postflop')]:
            ttk.Radiobutton(modes,text=title,value=mode,variable=app.mode_var,
                            command=app._on_mode_change,style='Pill.TRadiobutton').pack(side='left',expand=True,fill='x')
        controls = tk.Frame(self.window, bg=app.BG)
        controls.pack(fill='x', pady=(0, 4))
        if hasattr(app, 'ocr_var'):
            ttk.Checkbutton(
                controls, text='Auto-read', variable=app.ocr_var, command=app._toggle_ocr
            ).pack(side='left', padx=(0, 12))
        if hasattr(app, 'auto_act_var'):
            ttk.Checkbutton(
                controls, text='Auto-click', variable=app.auto_act_var, command=app._toggle_auto_act
            ).pack(side='left')
        self.table = tk.StringVar(app.root)
        self.context = tk.StringVar(app.root)
        self.metrics = tk.StringVar(app.root)
        self.label(self.table,9,'#8b9bb4')
        self.label(self.context,11,app.FG)
        self.action = self.label(app.advice_var,19,app.FG,bold=True)
        self.label(app.advice_detail,10,'#a8b8d0')
        self.label(self.metrics,10,'#60a5fa')
        self.label(app.confidence_var,9,'#8b9bb4')
        if hasattr(app, 'auto_act_status_var'):
            self.label(app.auto_act_status_var,9,'#10b981')
        self.timer = None
        app.root.bind('<Unmap>',self.minimised,add='+')
        app.root.bind('<Map>',self.mapped,add='+')

    def label(self, variable, size, color, bold=False):
        widget = tk.Label(self.window,textvariable=variable,bg=self.app.BG,fg=color,
                          font=('Helvetica',size,'bold' if bold else 'normal'),
                          wraplength=332,justify='left',anchor='w')
        widget.pack(fill='x',pady=4)
        return widget

    def sync(self):
        app = self.app
        title = app._get_current_table_name() or 'No table connected'
        self.table.set(title.split(' - Logged In as ')[0])
        cards = ' '.join(app._exact_cards or ()) or 'Waiting for cards'
        context = cards + (' · ' + app.pos_var.get() if app.pos_var.get() else '')
        if app.mode == 'postflop':
            board = app.board_entry.get().strip() or 'Waiting for board'
            context += '\n' + board
            self.metrics.set(' · '.join(v.get() for v in (app.equity_var,app.outs_var,app.pot_odds_var)))
        else:
            self.metrics.set(app.table_amounts_var.get())
        self.context.set(context)
        self.action.configure(bg=app.advice_label.cget('bg'))

    def tick(self):
        self.timer = None
        if self.window.state() != 'withdrawn':
            self.sync()
            self.timer = self.app.root.after(250,self.tick)

    def show(self, hide_main=True):
        self.sync()
        if not self.placed:
            self.window.geometry(f'+{max(0,self.app.root.winfo_screenwidth()-380)}+32')
            self.placed = True
        self.window.deiconify()
        self.window.lift()
        if hide_main:
            self.app.settings_window.withdraw()
            self.app.root.withdraw()
        if self.timer is None:
            self.tick()

    def hide(self):
        self.window.withdraw()
        if self.timer is not None:
            self.app.root.after_cancel(self.timer)
            self.timer = None

    def restore(self):
        self.hide()
        self.app.root.deiconify()
        self.app.root.lift()

    def minimised(self,event):
        if event.widget == self.app.root:
            self.app.root.after_idle(self.check_minimised)

    def check_minimised(self):
        if self.app.root.state() == 'iconic' and self.on_minimise.get():
            self.show(hide_main=False)

    def mapped(self,event):
        if event.widget == self.app.root and self.app.root.state() == 'normal':
            self.hide()

    def close(self):
        self.hide()
        self.window.destroy()
