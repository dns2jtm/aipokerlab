"""Native presentation layer for the RTA overlay; detection stays in rta.py."""
import sys
import tkinter as tk
from tkinter import ttk
import ranges

# ── Modern Design System ──────────────────────────────────────────
# Palette: deep navy base, elevated surfaces, electric accent
SURFACE = '#1a2332'          # card / section background
SURFACE_HOVER = '#1e2d42'    # hover state
SURFACE_ELEVATED = '#1e2d42' # elevated card
MUTED = '#8b9bb4'             # secondary text
MUTED_LIGHT = '#a8b8d0'       # slightly brighter muted
BORDER = '#243447'            # subtle border
BORDER_LIGHT = '#2a3d56'      # lighter border for focus
MAX_CONTENT_WIDTH = 640
TOOLTIP_BG = '#1e2d42'
TOOLTIP_FG = '#eef4fc'
ERROR_FG = '#f87171'
SUCCESS_FG = '#34d399'
ACCENT = '#3b82f6'            # electric blue
ACCENT_HOVER = '#60a5fa'
ACCENT_BG = '#1e3a5f'         # accent background tint

# Typography scale
FONT_DISPLAY = ('SF Pro Display', 22)
FONT_TITLE = ('SF Pro Display', 13)
FONT_BODY = ('SF Pro Text', 11)
FONT_LABEL = ('SF Pro Text', 10)
FONT_MONO = ('SF Mono', 11)
FONT_MONO_SM = ('SF Mono', 8)


def label(parent, text='', **kw):
    # Default to modern body font; caller can override via **kw
    if 'font' not in kw:
        kw['font'] = ('Helvetica', 11)
    if 'fg' not in kw:
        kw['fg'] = MUTED
    return tk.Label(parent, text=text, bg=parent.cget('bg'), **kw)


def label_muted(parent, text='', **kw):
    kw.setdefault('fg', MUTED)
    kw.setdefault('font', ('Helvetica', 10))
    return tk.Label(parent, text=text, bg=parent.cget('bg'), **kw)


def label_title(parent, text='', **kw):
    kw.setdefault('fg', MUTED_LIGHT)
    kw.setdefault('font', ('Helvetica', 10, 'bold'))
    return tk.Label(parent, text=text, bg=parent.cget('bg'), **kw)


def row(parent):
    frame = tk.Frame(parent, bg=parent.cget('bg'))
    frame.pack(fill='x', pady=4)
    return frame


def section(parent, title):
    # Modern card: slightly more padding, softer border, letter-spaced title
    frame = tk.Frame(parent, bg=SURFACE, padx=18, pady=14,
                     highlightbackground=BORDER, highlightthickness=1)
    # Title with tracking — use label_title for refined look
    title_text = '  '.join(title.upper()) if len(title) < 20 else title.upper()
    # Keep original title for short names, spaced for longer
    display = title.upper()
    lbl = tk.Label(frame, text=display, bg=SURFACE, fg=MUTED,
                   font=('Helvetica', 9, 'bold'))
    lbl.pack(anchor='w', pady=(0, 12))
    return frame


def card_frame(parent, padx=18, pady=14):
    """Bare card without title — for custom layouts."""
    return tk.Frame(parent, bg=SURFACE, padx=padx, pady=pady,
                    highlightbackground=BORDER, highlightthickness=1)


def segments(parent, variable, options, command):
    frame = row(parent)
    buttons = {}
    for i, (text, value) in enumerate(options):
        button = ttk.Radiobutton(frame, text=text, value=value, variable=variable,
                                 command=command, style='Segment.TRadiobutton')
        button.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 4, 0))
        frame.columnconfigure(i, weight=1, uniform='segment')
        buttons[value] = button
    return buttons


def pill_segments(parent, variable, options, command):
    """Pill-style segments with rounded appearance via padding."""
    outer = tk.Frame(parent, bg='#111a27', padx=3, pady=3)
    outer.pack(fill='x', pady=4)
    buttons = {}
    for i, (text, value) in enumerate(options):
        btn = ttk.Radiobutton(outer, text=text, value=value, variable=variable,
                              command=command, style='Pill.TRadiobutton')
        btn.grid(row=0, column=i, sticky='ew', padx=2)
        outer.columnconfigure(i, weight=1, uniform='pill')
        buttons[value] = btn
    return buttons


def entry(parent, width=12):
    e = tk.Entry(parent, width=width, bg='#0f1a2a', fg='#eef4fc',
                 insertbackground='#60a5fa', relief='flat', bd=0,
                 highlightbackground=BORDER, highlightcolor=ACCENT,
                 highlightthickness=1, font=('Menlo', 13),
                 selectbackground='#1e3a5f', selectforeground='#eef4fc')
    # Add internal padding via border
    e.configure(bd=8)
    return e


# ------------------------------------------------------------------ helpers

def _make_tooltip(widget, text_var_or_str):
    """Simple tooltip that follows the widget on hover."""
    tip = None
    def show(event=None):
        nonlocal tip
        if tip is not None:
            return
        text = text_var_or_str.get() if hasattr(text_var_or_str, 'get') else text_var_or_str
        if not text:
            return
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(tip, text=text, bg=TOOLTIP_BG, fg=TOOLTIP_FG,
                 font=('Helvetica', 10), padx=8, pady=4,
                 relief='solid', bd=1).pack()
    def hide(event=None):
        nonlocal tip
        if tip is not None:
            try:
                tip.destroy()
            except Exception:
                pass
            tip = None
    widget.bind('<Enter>', show)
    widget.bind('<Leave>', hide)
    return hide


def diagram_positions(hero, detected=None, manual=False):
    """Seat IDs follow the capture: top clockwise, hero always seat 3."""
    if detected and detected.get(3) == hero and not manual:
        return dict(detected)
    order = ['BTN', 'SB', 'BB', 'UTG', 'MP', 'CO']
    if hero not in order:
        return {}
    start = order.index(hero)
    return {seat: order[(start + seat - 3) % 6] for seat in range(6)}


def _build_table_diagram(parent, app):
    frame = tk.Frame(parent, bg=SURFACE)
    frame.pack(fill='x', pady=(4, 8))
    canvas = tk.Canvas(frame, width=340, height=170, bg=SURFACE,
                       highlightthickness=0, bd=0)
    canvas.pack()
    canvas.create_oval(70, 30, 270, 140, fill='#162635', outline=BORDER)
    center = canvas.create_text(170, 85, text='TABLE', fill=MUTED,
                               font=('Helvetica', 8, 'bold'))
    locations = [(170,20),(278,51),(278,110),(170,142),(61,110),(61,51)]
    items = {}
    for seat, (x,y) in enumerate(locations):
        box = canvas.create_rectangle(x-39,y-12,x+39,y+12,fill='#111a27',outline=BORDER)
        text = canvas.create_text(x,y,text='—',fill=MUTED,font=('Helvetica',10,'bold'))
        items[seat] = (box,text)
    dealer = canvas.create_text(0,0,text='D',fill='#ffcc00',font=('Helvetica',10,'bold'),state='hidden')

    def update():
        hero = app.pos_var.get()
        detected = getattr(app, '_preflop_context', {}).get('positions', {})
        mapping = diagram_positions(hero, detected, getattr(app, '_manual_position', False))
        app._diagram_positions = mapping
        canvas.itemconfigure(center, text='DETECTED SEATS' if detected == mapping and mapping else 'YOUR SEAT AT BOTTOM')
        canvas.itemconfigure(dealer,state='hidden')
        for seat,(box,text) in items.items():
            position = mapping.get(seat)
            caption = (position + ' · You') if seat == 3 and position else position or '—'
            canvas.itemconfigure(text,text=caption,fill='#ffffff' if seat == 3 else MUTED_LIGHT)
            canvas.itemconfigure(box,fill=ACCENT_BG if seat == 3 else '#111a27',outline=ACCENT if seat == 3 else BORDER)
            if position == 'BTN':
                x,y=locations[seat]
                canvas.coords(dealer,x+47,y)
                canvas.itemconfigure(dealer,state='normal')
    app._update_table_diagram = update
    app._diagram_canvas = canvas
    app.pos_var.trace_add('write', lambda *_: update())
    update()
    return frame


def build(app, multitable=False):
    root = app.root
    style = ttk.Style(root)
    style.theme_use('clam')
    # Base
    style.configure('.', font=('Helvetica', 11), background=SURFACE, foreground=app.FG)
    # Buttons — modern with subtle hover
    style.configure('TButton', padding=(12, 8), background='#243447', borderwidth=0,
                    font=('Helvetica', 11), foreground='#eef4fc')
    style.map('TButton', background=[('active', '#2a3d56'), ('pressed', '#1e2d42')],
              foreground=[('disabled', '#4a5a72')])
    # Accent button (for primary actions)
    style.configure('Accent.TButton', padding=(14, 9), background=ACCENT, borderwidth=0,
                    font=('Helvetica', 11, 'bold'), foreground='#ffffff')
    style.map('Accent.TButton', background=[('active', ACCENT_HOVER), ('pressed', '#2563eb')])
    # Ghost button (subtle)
    style.configure('Ghost.TButton', padding=(10, 7), background=SURFACE, borderwidth=0,
                    font=('Helvetica', 10), foreground=MUTED)
    style.map('Ghost.TButton', background=[('active', SURFACE_HOVER)], foreground=[('active', '#eef4fc')])
    # Checkbutton
    style.configure('TCheckbutton', background=SURFACE, padding=(0, 5), font=('Helvetica', 11))
    style.map('TCheckbutton', background=[('active', SURFACE)], indicatorbackground=[('selected', ACCENT)])
    # Combobox
    style.configure('TCombobox', fieldbackground='#0f1a2a', background=BORDER,
                    foreground=app.FG, padding=8, arrowcolor=MUTED)
    style.map('TCombobox', fieldbackground=[('readonly', '#0f1a2a')],
              foreground=[('readonly', app.FG)], selectbackground=[('readonly', '#0f1a2a')],
              selectforeground=[('readonly', app.FG)])
    # Scrollbar — minimal
    style.configure('TScrollbar', troughcolor=app.BG, background='#1e2d42', borderwidth=0, arrowsize=0)
    style.map('TScrollbar', background=[('active', '#243447')])
    # Segment buttons — modern pill-like
    style.layout('Segment.TRadiobutton', [('Radiobutton.padding', {'sticky': 'nswe', 'children': [
        ('Radiobutton.label', {'sticky': 'nswe'})]})])
    style.configure('Segment.TRadiobutton', background='#1a2535', foreground=MUTED,
                    padding=(10, 10), anchor='center', font=('Helvetica', 11, 'bold'),
                    borderwidth=0, relief='flat')
    style.map('Segment.TRadiobutton', background=[('selected', '#1e3a5f'), ('active', '#1e2d42')],
              foreground=[('selected', '#60a5fa'), ('active', '#eef4fc')])
    # Pill variant — for tab navigation
    style.layout('Pill.TRadiobutton', [('Radiobutton.padding', {'sticky': 'nswe', 'children': [
        ('Radiobutton.label', {'sticky': 'nswe'})]})])
    style.configure('Pill.TRadiobutton', background='#111a27', foreground=MUTED,
                    padding=(10, 8), anchor='center', font=('Helvetica', 10, 'bold'),
                    borderwidth=0, relief='flat')
    style.map('Pill.TRadiobutton', background=[('selected', ACCENT), ('active', '#1e2d42')],
              foreground=[('selected', '#ffffff'), ('active', '#eef4fc')])
    root.option_add('*TCombobox*Listbox.background', '#1a2332')
    root.option_add('*TCombobox*Listbox.foreground', app.FG)
    root.option_add('*TCombobox*Listbox.selectBackground', '#1e3a5f')
    root.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')

    header = tk.Frame(root, bg=app.BG, padx=20, pady=16)
    header.pack(fill='x')
    # Logo mark — small accent dot + wordmark
    logo_frame = tk.Frame(header, bg=app.BG)
    logo_frame.pack(side='left')
    dot = tk.Canvas(logo_frame, width=10, height=10, bg=app.BG, highlightthickness=0, bd=0)
    dot.pack(side='left', padx=(0, 8))
    dot.create_oval(1, 1, 9, 9, fill=ACCENT, outline='')
    tk.Label(logo_frame, text='RTA', bg=app.BG, fg=app.FG,
             font=('Helvetica', 20, 'bold')).pack(side='left')
    tk.Label(logo_frame, text='TABLE COMPANION', bg=app.BG, fg=MUTED,
             font=('Helvetica', 9)).pack(side='left', padx=(10, 0), pady=(4, 0))
    # Header actions — ghost style
    ttk.Button(header, text='?', width=3, command=app._show_help, style='Ghost.TButton').pack(side='right', padx=(6, 0))
    ttk.Button(header, text='Settings', command=app._open_settings, style='Ghost.TButton').pack(side='right')
    ttk.Button(header, text='Compact', command=lambda: app.compact.show(), style='Ghost.TButton').pack(side='right', padx=6)
    app.mode_var = tk.StringVar(value='preflop')
    tabs = tk.Frame(root, bg=app.BG, padx=20)
    tabs.pack(fill='x', pady=(0, 14))
    # Pill container for tabs
    pill_outer = tk.Frame(tabs, bg='#111a27', padx=4, pady=4)
    pill_outer.pack(fill='x')
    for text, val in [('Preflop', 'preflop'), ('Postflop', 'postflop'), ('Analytics', 'analytics')]:
        btn = ttk.Radiobutton(pill_outer, text=text, value=val, variable=app.mode_var,
                              command=app._on_mode_change, style='Pill.TRadiobutton')
        btn.pack(side='left', fill='x', expand=True, padx=2)

    footer = tk.Frame(root, bg='#0d1520', padx=20, pady=10)
    footer.pack(side='bottom', fill='x')
    shortcut = '\u2318 Shift Space' if sys.platform == 'darwin' else 'Ctrl Space'
    tk.Label(footer, text=f'{shortcut}  \u00b7  Esc hide  \u00b7  ? help  \u00b7  H focus', bg='#0d1520', fg='#4a5a72',
             font=('Helvetica', 9)).pack(side='left')
    app.memory_label = tk.Label(footer, text='Memory: \u2014', bg='#0d1520', fg='#4a5a72', font=('Helvetica', 9))
    app.memory_label.pack(side='right')

    viewport = tk.Frame(root, bg=app.BG)
    viewport.pack(fill='both', expand=True)
    app.content_canvas = tk.Canvas(viewport, bg=app.BG, highlightthickness=0, bd=0)
    scroll = ttk.Scrollbar(viewport, orient='vertical', command=app.content_canvas.yview)
    scroll.pack(side='right', fill='y')
    app.content_canvas.pack(side='left', fill='both', expand=True)
    app.content_canvas.configure(yscrollcommand=scroll.set)
    # Centered max-width container inside canvas
    body_outer = tk.Frame(app.content_canvas, bg=app.BG)
    window = app.content_canvas.create_window(0, 0, anchor='nw', window=body_outer)
    body = tk.Frame(body_outer, bg=app.BG, padx=20)
    body.pack(fill='both', expand=True)
    # Debounced scrollregion update
    app._scroll_after_id = None
    def schedule_scrollregion(event=None):
        if app._scroll_after_id is not None:
            try:
                root.after_cancel(app._scroll_after_id)
            except Exception:
                pass
        def do_update():
            app._scroll_after_id = None
            try:
                app.content_canvas.configure(scrollregion=app.content_canvas.bbox('all'))
            except Exception:
                pass
        app._scroll_after_id = root.after(50, do_update)
    body_outer.bind('<Configure>', schedule_scrollregion)
    body.bind('<Configure>', schedule_scrollregion)
    def on_canvas_configure(event):
        # Clamp content width to MAX_CONTENT_WIDTH, center it
        w = event.width
        content_w = min(w, MAX_CONTENT_WIDTH)
        # Center body_outer by adjusting window width and position
        app.content_canvas.itemconfigure(window, width=w)
        # body width is content_w, centered via padding
        pad = max(0, (w - content_w) // 2)
        body_outer.configure(padx=pad)
        try:
            body.configure(width=content_w - 40)
        except Exception:
            pass
    app.content_canvas.bind('<Configure>', on_canvas_configure)
    def wheel(event):
        if app.content_canvas.winfo_height() < body_outer.winfo_reqheight():
            if sys.platform == 'darwin':
                delta = event.delta
            else:
                delta = event.delta / 120
                # Windows sends 120 per notch, Linux may send smaller
                if abs(delta) < 1:
                    delta = 1 if delta > 0 else -1
            app.content_canvas.yview_scroll(-int(delta), 'units')
    root.bind('<MouseWheel>', wheel, add='+')
    root.bind('<Button-4>', lambda e: app.content_canvas.yview_scroll(-1, 'units') if sys.platform != 'darwin' else None, add='+')
    root.bind('<Button-5>', lambda e: app.content_canvas.yview_scroll(1, 'units') if sys.platform != 'darwin' else None, add='+')
    body.columnconfigure(0, weight=1)

    source = section(body, 'Table & capture')
    source.grid(row=0, column=0, sticky='ew', pady=(0, 12))
    app.table_combo = ttk.Combobox(source, state='readonly', width=22)
    app.table_combo.set('No table connected')
    app.table_combo.pack(fill='x')
    app.table_combo.bind('<<ComboboxSelected>>', app._on_table_select)
    app.follow_table_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(source, text='Follow frontmost poker table', variable=app.follow_table_var,
                    command=app._on_follow_table_change).pack(anchor='w', pady=(4, 0))
    app.table_connection_var = tk.StringVar(value='Looking for poker tables…')
    label(source, textvariable=app.table_connection_var, wraplength=470, justify='left').pack(anchor='w', pady=(4, 0))
    app._ocr_controls = row(source)
    app.ocr_var = tk.BooleanVar(value=False)
    app.ocr_check = ttk.Checkbutton(app._ocr_controls, text='Auto-read cards, bets & stacks',
                                   variable=app.ocr_var, command=app._toggle_ocr)
    app.ocr_check.pack(side='left')
    app._auto_act_controls = row(source)
    app.auto_act_var = tk.BooleanVar(value=bool(app._config.get('auto_act_enabled', False)))
    app.auto_act_check = ttk.Checkbutton(
        app._auto_act_controls,
        text='Autonomous action execution (Auto-click)',
        variable=app.auto_act_var,
        command=app._toggle_auto_act,
    )
    app.auto_act_check.pack(side='left')
    app.auto_act_status_var = tk.StringVar(
        value='Autonomous mode: Armed' if app.auto_act_var.get() else 'Autonomous mode: Off'
    )
    app.auto_act_status_label = label(source, textvariable=app.auto_act_status_var, wraplength=470, justify='left')
    app.auto_act_status_label.pack(anchor='w', pady=(2, 0))
    # Unified OCR status bar with pulse + retry
    app.ocr_status_frame = row(source)
    app.ocr_status_icon = label(app.ocr_status_frame, '\u25cf')
    app.ocr_status_icon.pack(side='left', padx=(0, 8))
    app.ocr_status = label(app.ocr_status_frame, 'Manual input \u00b7 enter a hand below', anchor='w', justify='left', wraplength=400)
    app.ocr_status.pack(side='left', fill='x', expand=True)
    app.ocr_retry_btn = ttk.Button(app.ocr_status_frame, text='Retry', command=lambda: app._retry_ocr())
    # hidden by default, shown on error
    app._ocr_pulse_after = None
    app._ocr_pulse_on = False
    units = row(source)
    label(units, 'Table shows').pack(side='left', padx=(0, 10))
    app.table_units_var = tk.StringVar(value='chips')
    segments(units, app.table_units_var, [('Chips', 'chips'), ('BB', 'bb')], app._on_table_units_change)
    blinds = row(source)
    label(blinds, 'Big blind (chips)').pack(side='left', padx=(0, 10))
    app.big_blind_var = tk.StringVar()
    app.big_blind_entry = entry(blinds, 8)
    app.big_blind_entry.configure(textvariable=app.big_blind_var)
    app.big_blind_entry.pack(side='left')
    app.big_blind_entry.bind('<Return>', app._on_big_blind_change)
    app.big_blind_entry.bind('<FocusOut>', app._on_big_blind_change)
    label(blinds, 'Auto · edit to override').pack(side='left', padx=8)
    app.auto_stack_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(source, text='Automatically select stack-depth range', variable=app.auto_stack_var,
                    command=app._refresh).pack(anchor='w')
    app.table_amounts_var = tk.StringVar(value='Waiting for blinds and stacks')
    label(source, textvariable=app.table_amounts_var, wraplength=470, justify='left').pack(anchor='w', pady=(6, 0))

    app.play_frame = tk.Frame(body, bg=app.BG)
    app.play_frame.grid(row=1, column=0, sticky='ew')
    play = app.play_frame
    play.columnconfigure(0, weight=1)
    app.evidence_frame = section(play, 'Your hand')
    app.evidence_frame.grid(row=0, column=0, sticky='ew', pady=(0, 12))
    handrow = row(app.evidence_frame)
    app.card_tiles = []
    for _ in range(2):
        card = tk.Label(handrow, text='\u2014', bg='#1e2d42', fg='#6b7fa0',
                        font=('Helvetica', 26, 'bold'), width=3, height=2,
                        relief='flat', bd=0, highlightbackground=BORDER, highlightthickness=1)
        card.pack(side='left', padx=(0, 8))
        app.card_tiles.append(card)
    manual = tk.Frame(handrow, bg=SURFACE)
    manual.pack(side='left', padx=12, fill='x', expand=True)
    label(manual, 'HAND INPUT').pack(anchor='w', pady=(0, 4))
    # Entry with autocomplete
    entry_frame = tk.Frame(manual, bg=SURFACE)
    entry_frame.pack(fill='x')
    app.hand_entry = entry(entry_frame)
    app.hand_entry.pack(fill='x')
    app.hand_entry.bind('<KeyRelease>', app._on_hand_type)
    app.hand_entry.bind('<FocusIn>', lambda e: app._show_autocomplete())
    app.hand_entry.bind('<FocusOut>', lambda e: app.root.after(150, app._hide_autocomplete))
    app.hand_entry.bind('<Down>', lambda e: app._autocomplete_next())
    app.hand_entry.bind('<Up>', lambda e: app._autocomplete_prev())
    app.hand_entry.bind('<Return>', lambda e: app._autocomplete_select())
    app.hand_entry.bind('<Escape>', lambda e: app._hide_autocomplete())
    # Autocomplete listbox (hidden by default)
    app.autocomplete_listbox = tk.Listbox(manual, height=6, bg='#0f1a2a', fg='#eef4fc',
                                          selectbackground='#1e3a5f', selectforeground='#60a5fa',
                                          font=('Menlo', 11), relief='flat', bd=0,
                                          highlightbackground=BORDER, highlightthickness=1,
                                          activestyle='none')
    app.autocomplete_listbox.bind('<Button-1>', lambda e: app._autocomplete_click(e))
    app._autocomplete_visible = False
    app._autocomplete_items = []
    app._autocomplete_index = -1
    app.hand_hint = label(manual, 'e.g. AKs, JJ, T9o', anchor='w')
    app.hand_hint.pack(anchor='w', pady=(5, 0))
    # Inline validation label
    app.hand_error = tk.Label(manual, text='', bg=SURFACE, fg=ERROR_FG,
                              font=('Helvetica', 10), anchor='w', justify='left')
    app.hand_error.pack(anchor='w', pady=(2, 0))
    # Recent hands chips
    app.recent_frame = tk.Frame(manual, bg=SURFACE)
    app.recent_frame.pack(fill='x', pady=(6, 0))
    app.exact_cards_label = label(app.evidence_frame, 'Cards: unknown')
    app.exact_cards_label.pack(anchor='w', pady=(6, 0))

    app.spot_frame = section(play, 'Situation')
    app.spot_frame.grid(row=1, column=0, sticky='ew', pady=(0, 12))
    app.pos_var = tk.StringVar(value='BTN')
    label(app.spot_frame, 'Your position').pack(anchor='w')
    # Table diagram + fallback segments
    _build_table_diagram(app.spot_frame, app)
    app.pos_buttons = segments(app.spot_frame, app.pos_var, [(p,p) for p in ranges.POSITIONS_6MAX], app._on_position_change)
    app.kind_var = tk.StringVar(value='open')
    app.preflop_status_var = tk.StringVar(value='Auto mode tracks action from the start of a hand')
    label(app.spot_frame, textvariable=app.preflop_status_var, wraplength=470, justify='left').pack(anchor='w')
    label(app.spot_frame, 'Action before you').pack(anchor='w', pady=(7, 0))
    segments(app.spot_frame, app.kind_var, [('First in','open'), ('Open','facing_open'),
        ('Iso-Raise','iso_raise'), ('Squeeze','squeeze'), ('3-bet','facing_3bet'), ('4-bet','facing_4bet')], app._on_spot_change)
    # Let the opener controls request their full height at every display scale.
    app.vs_row_container = tk.Frame(app.spot_frame, bg=SURFACE)
    app.vs_row_container.pack(fill='x')
    app.vs_row = tk.Frame(app.vs_row_container, bg=SURFACE)
    label(app.vs_row, 'Opener position').pack(anchor='w', pady=(5, 0))
    app.vs_var = tk.StringVar(value='CO')
    segments(app.vs_row, app.vs_var, [(p,p) for p in ['UTG','MP','CO','BTN','SB']], app._on_spot_change)

    app.postflop_frame = section(play, 'Board & amounts')
    app.postflop_frame.grid(row=1, column=0, sticky='ew', pady=(0, 12))
    auto = row(app.postflop_frame)
    app.postflop_autodetect_var = tk.BooleanVar(value=False)
    app.postflop_autodetect_check = ttk.Checkbutton(auto, text='Auto-detect board & amounts',
        variable=app.postflop_autodetect_var, command=app._toggle_postflop_autodetect)
    app.postflop_autodetect_check.pack(side='left')
    app.detection_status_frame = row(app.postflop_frame)
    app.detection_status_icon = label(app.detection_status_frame, '\u25cf')
    app.detection_status_icon.pack(side='left', padx=(0,6))
    app.detection_status_label = label(app.detection_status_frame, 'Ready')
    app.detection_status_label.pack(side='left')
    board = row(app.postflop_frame)
    label(board, 'Board').pack(side='left', padx=(0, 10))
    app.board_entry = entry(board, 17)
    app.board_entry.pack(side='left', fill='x', expand=True)
    app.board_entry.bind('<KeyRelease>', app._on_postflop_key)
    app.board_detect_indicator = label(board)
    app.board_detect_indicator.pack(side='left')
    app.street_indicator = label(board)
    app.street_indicator.pack(side='left', padx=5)
    label(app.postflop_frame, 'Use exact suits, e.g. Qd Jd 8s').pack(anchor='w')
    app.amount_units_var = tk.StringVar(value='chips')
    unitrow = row(app.postflop_frame)
    label(unitrow, 'Amounts in').pack(side='left', padx=(0, 10))
    segments(unitrow, app.amount_units_var, [('Chips', 'chips'), ('BB', 'bb')], app._on_amount_units_change)
    amounts = row(app.postflop_frame)
    for key, title in [('pot', 'Pot'), ('call', 'To call')]:
        label(amounts, title).pack(side='left', padx=(0,8))
        field = entry(amounts, 8)
        field.pack(side='left', fill='x', expand=True)
        field.bind('<KeyRelease>', app._on_postflop_key)
        setattr(app, key+'_entry', field)
        indicator = label(amounts)
        indicator.pack(side='left', padx=(0,8))
        setattr(app, key+'_detect_indicator', indicator)
    app.action_indicator = label(app.postflop_frame)
    app.action_indicator.pack(anchor='w')

    advice = section(play, 'Guidance')
    advice.grid(row=2, column=0, sticky='ew', pady=(0,12))
    app.advice_var = tk.StringVar(value='Enter your hand')
    app.advice_detail = tk.StringVar()
    app.confidence_var = tk.StringVar()
    # Hero guidance label — larger, more breathing room, subtle inner accent
    app.advice_label = tk.Label(advice, textvariable=app.advice_var, bg=app.FOLD_C, fg=app.FG,
                                font=('Helvetica', 22, 'bold'), padx=16, pady=16, anchor='w', justify='left', wraplength=465)
    app.advice_label.pack(fill='x')
    app.detail_label = tk.Label(advice, textvariable=app.advice_detail, bg=SURFACE, fg=MUTED_LIGHT,
                                font=('Helvetica',11), anchor='w', justify='left', wraplength=465)
    app.detail_label.pack(fill='x', pady=(10,0))
    # Confidence bar — slightly thicker, rounded feel
    app.confidence_bar = tk.Canvas(advice, height=3, bg='#111a27', highlightthickness=0, bd=0)
    app.confidence_bar.pack(fill='x', pady=(10, 0))
    meta = row(advice)
    app.confidence_label = tk.Label(meta, textvariable=app.confidence_var, bg=SURFACE,
                                    fg='#4a5a72', font=('Helvetica',9))
    app.confidence_label.pack(side='left')
    app.quick_action_btn = ttk.Button(meta, text='Copy', command=app._copy_action, style='Ghost.TButton')
    app.quick_action_btn.pack(side='right')
    feedback = row(advice)
    app.feedback_row = feedback
    app.followed_btn = ttk.Button(feedback, text='✓ Followed', command=lambda: app._record_user_action(True), style='Ghost.TButton')
    app.followed_btn.pack(side='left', padx=(0, 4))
    app.deviated_btn = ttk.Button(feedback, text='✗ Deviated', command=lambda: app._record_user_action(False), style='Ghost.TButton')
    app.deviated_btn.pack(side='left', padx=(0, 8))
    app.won_btn = ttk.Button(feedback, text='Won', command=lambda: app._record_hand_result('win'), style='Ghost.TButton')
    app.won_btn.pack(side='left', padx=(0, 4))
    app.lost_btn = ttk.Button(feedback, text='Lost', command=lambda: app._record_hand_result('loss'), style='Ghost.TButton')
    app.lost_btn.pack(side='left', padx=(0, 8))
    app.feedback_status_var = tk.StringVar(value='')
    app.feedback_status_label = tk.Label(feedback, textvariable=app.feedback_status_var, bg=SURFACE,
                                         fg=SUCCESS_FG, font=('Helvetica', 9))
    app.feedback_status_label.pack(side='left')
    app.postflop_info_frame = row(advice)
    for key, title in [('equity','Equity'), ('outs','Outs'), ('pot_odds','Pot odds')]:
        var = tk.StringVar(value=title+': \u2014')
        widget = tk.Label(app.postflop_info_frame, textvariable=var, bg=SURFACE,
                           fg=app.ACCENT, font=('Helvetica',12,'bold'))
        widget.pack(side='left', expand=True)
        setattr(app,key+'_var',var)
        setattr(app,key+'_label',widget)

    app.range_panel = section(play, 'Preflop ranges')
    app.range_panel.grid(row=3, column=0, sticky='ew', pady=(0,12))
    # Filter toggles for grid
    filter_row = row(app.range_panel)
    app.grid_filter_var = tk.StringVar(value='all')
    for text, val in [('All', 'all'), ('Raise', 'raise'), ('Call', 'call'), ('Fold', 'fold')]:
        ttk.Radiobutton(filter_row, text=text, value=val, variable=app.grid_filter_var,
                        command=app._on_grid_filter_change, style='Segment.TRadiobutton').pack(side='left', padx=(0, 4), fill='x', expand=True)
    app.show_range_var = tk.BooleanVar(value=False)
    app.range_toggle = ttk.Checkbutton(app.range_panel, text='Show hand matrix', variable=app.show_range_var,
                                       command=app._toggle_range_grid)
    app.range_toggle.pack(anchor='w', pady=(6, 0))
    app.grid_frame = tk.Frame(app.range_panel, bg=SURFACE)
    app.cells, app.cell_labels, app.cell_mix_indicators = {}, [], {}
    for i,r1 in enumerate(ranges.RANKS):
        cells=[]
        for j,r2 in enumerate(ranges.RANKS):
            hand = r1+r2+'s' if i<j else r1+r2 if i==j else r2+r1+'o'
            cell = tk.Label(app.grid_frame, text=hand, font=('Menlo',8), bg=app.GRID_EMPTY,
                             fg='#5a6d8a', width=3, height=1, cursor='hand2', takefocus=True,
                             relief='flat', bd=0)
            cell.grid(row=i, column=j, sticky='nsew', padx=1, pady=1, ipady=4)
            mix_bar = tk.Frame(cell, height=2, bg=app.GRID_EMPTY, bd=0, highlightthickness=0)
            mix_bar.place(relx=0.0, rely=1.0, relwidth=1.0, anchor='sw')
            app.cell_mix_indicators[hand] = mix_bar
            cell.bind('<Button-1>', lambda e,h=hand: app._select_hand(h))
            cell.bind('<Return>', lambda e,h=hand: app._select_hand(h))
            cell.bind('<space>', lambda e,h=hand: app._select_hand(h))
            # Hover tooltip
            cell.bind('<Enter>', lambda e,h=hand: app._on_grid_hover(h, e))
            cell.bind('<Leave>', lambda e: app._on_grid_leave(e))
            cells.append(cell)
            app.cells[hand]=cell
        app.cell_labels.append(cells)
        app.grid_frame.columnconfigure(i, weight=1, uniform='cell')
    legend = tk.Frame(app.grid_frame, bg=SURFACE)
    legend.grid(row=13, column=0, columnspan=13, sticky='w', pady=(8,0))
    for title,color in [('Raise',app.RAISE_C),('Call',app.CALL_C),('Mixed','#f59e0b'),('Fold',app.GRID_EMPTY),('Selected',app.ACCENT)]:
        tk.Label(legend,text='\u25cf '+title,bg=SURFACE,fg=color if title!='Fold' else MUTED,
                 font=('Helvetica',10)).pack(side='left',padx=(0,12))
    # Grid tooltip popup
    app._grid_tooltip = None
    app._grid_tooltip_after = None

    app.analytics_frame = section(body, 'Session analytics')
    app.analytics_frame.grid(row=1, column=0, sticky='ew', pady=(0,12))
    # Empty state label (shown when no hands)
    app.analytics_empty = tk.Label(app.analytics_frame, text='No hands logged yet\nPlay a hand to see stats here.',
                                   bg=SURFACE, fg=MUTED, font=('Helvetica', 12),
                                   justify='center', pady=20)
    stats = row(app.analytics_frame)
    app._analytics_stats_row = stats
    app.analytics_labels = {}
    for i,(key,title) in enumerate([('total_hands','Hands logged'),('gto_adherence','Range adherence'),
                                    ('wins','Wins'),('losses','Losses'),('win_rate','Win rate'),('followed','Guidance followed'),
                                    ('net_bb','Net BB'),('bb_per_100','BB / 100')]):
        tile = tk.Frame(stats,bg='#1e2d42',padx=16,pady=14, highlightbackground=BORDER, highlightthickness=1)
        tile.grid(row=i//2,column=i%2,sticky='ew',padx=4,pady=4)
        tk.Label(tile,text=title.upper(), bg='#1e2d42', fg=MUTED, font=('Helvetica', 8, 'bold')).pack(anchor='w')
        val=tk.Label(tile,text='\u2014',bg='#1e2d42',fg=app.FG,font=('Helvetica',24,'bold'))
        val.pack(anchor='w',pady=(8,0))
        app.analytics_labels[key]=val
    for i in range(2): stats.columnconfigure(i,weight=1,uniform='stat')
    app._analytics_dist_label = label(app.analytics_frame,'ACTION DISTRIBUTION')
    app._analytics_dist_label.pack(anchor='w',pady=(16,6))
    app.action_labels={}
    app._analytics_action_rows = []
    for action in ['RAISE','CALL','FOLD','CHECK']:
        line=row(app.analytics_frame)
        app._analytics_action_rows.append(line)
        label(line,action,width=8,anchor='w').pack(side='left')
        # Canvas bar instead of text blocks
        bar_canvas = tk.Canvas(line, height=14, bg=SURFACE, highlightthickness=0, bd=0)
        bar_canvas.pack(side='left', fill='x', expand=True, padx=(8, 8))
        pct_label = label(line, '\u2014', anchor='w', width=6)
        pct_label.pack(side='left')
        app.action_labels[action] = (bar_canvas, pct_label)
    app._analytics_pos_label = label(app.analytics_frame, 'POSITION BREAKDOWN')
    app._analytics_pos_label.pack(anchor='w', pady=(16, 6))
    app._analytics_pos_frame = row(app.analytics_frame)
    app.position_stat_labels = {}
    for idx, pos in enumerate(['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB']):
        pos_tile = tk.Frame(app._analytics_pos_frame, bg='#1e2d42', padx=10, pady=8,
                            highlightbackground=BORDER, highlightthickness=1)
        pos_tile.grid(row=idx // 3, column=idx % 3, sticky='ew', padx=3, pady=3)
        tk.Label(pos_tile, text=pos, bg='#1e2d42', fg=MUTED, font=('Helvetica', 8, 'bold')).pack(anchor='w')
        pos_val = tk.Label(pos_tile, text='0 hands', bg='#1e2d42', fg=app.FG, font=('Helvetica', 10, 'bold'))
        pos_val.pack(anchor='w', pady=(2, 0))
        app.position_stat_labels[pos] = pos_val
    for col_idx in range(3):
        app._analytics_pos_frame.columnconfigure(col_idx, weight=1, uniform='pos_stat')
    exports=row(app.analytics_frame)
    app._analytics_exports = exports
    for key,title,command in [('export_json_btn','Export JSON',app._export_json),
                              ('export_csv_btn','Export CSV',app._export_csv),
                              ('refresh_analytics_btn','Refresh',app._refresh_analytics),
                              ('clear_analytics_btn','Clear History',app._clear_analytics_history)]:
        button=ttk.Button(exports,text=title,command=command)
        button.pack(side='left',padx=(0,6))
        setattr(app,key,button)

    from compact_view import CompactGuidance
    app.compact = CompactGuidance(app)
    build_settings(app)
    app._update_memory_usage()
    root.bind('<Escape>', lambda e: (app._emergency_stop_auto_act() if getattr(app, 'auto_act_var', None) and app.auto_act_var.get() else None, root.withdraw()))
    root.protocol('WM_DELETE_WINDOW', app._on_close)
    # Keyboard shortcuts
    root.bind('<KeyPress>', app._on_key_shortcut, add='+')
    if multitable:
        app._multitable_manager.start_monitoring()
        # Poll on Tk's thread; worker callbacks must never wait on Tk while
        # the UI is reading the manager's table snapshot.
        app._update_table_list()


def build_settings(app):
    win = tk.Toplevel(app.root)
    win.withdraw()
    win.title('RTA \u00b7 Settings')
    win.configure(bg=app.BG, padx=18, pady=18)
    win.geometry('510x880')
    win.resizable(False, False)
    win.transient(app.root)
    win.protocol('WM_DELETE_WINDOW', app._close_settings)
    win.bind('<Escape>', lambda e: app._close_settings())
    app.settings_window=win
    strategy = section(win,'Strategy preferences')
    strategy.pack(fill='x',pady=(0,12))
    app.profile_var=tk.StringVar(value=app._config.get('profile','ABC'))
    segments(strategy,app.profile_var,[(p,p) for p in ['TAG','LAG','ABC','Aggressive']],app._on_strategy_change)
    label(strategy,'Stack depth').pack(anchor='w',pady=(8,0))
    app.stack_var=tk.StringVar(value=str(app._config.get('stack_depth',100)))
    segments(strategy,app.stack_var,[(f'{d} bb',str(d)) for d in [20,50,100,150]],app._on_stack_change)
    agg=row(strategy)
    label(agg,'Aggression').pack(side='left')
    app.aggression_var=tk.DoubleVar(value=app._config.get('aggression_factor',1.0))
    app.aggression_label=label(agg,f'{app.aggression_var.get():.1f}x')
    app.aggression_label.pack(side='right')
    app.aggression_scale=tk.Scale(agg,from_=0.5,to=2.0,resolution=0.1,showvalue=False,
        variable=app.aggression_var,orient='horizontal',command=app._on_aggression_change,
        bg=SURFACE,fg=app.FG,troughcolor=BORDER,highlightthickness=0,bd=0)
    app.aggression_scale.pack(side='right',fill='x',expand=True,padx=12)
    ttk.Button(strategy,text='Import ranges\u2026',command=app._import_ranges).pack(anchor='w',pady=(8,0))
    app.use_native_solver_var = tk.BooleanVar(value=bool(getattr(app, '_use_native_solver', app._config.get('use_native_solver', True))))
    app.use_native_solver_check = ttk.Checkbutton(
        strategy,
        text='Native Rust MCCFR postflop solver (ReBeL + blueprint)',
        variable=app.use_native_solver_var,
        command=app._on_native_solver_change,
    )
    app.use_native_solver_check.pack(anchor='w', pady=(8, 0))
    solver_budget = row(strategy)
    label(solver_budget, 'Subgame search budget').pack(side='left')
    app.native_search_ms_var = tk.IntVar(value=int(getattr(app, '_native_search_ms', app._config.get('native_search_ms', 250))))
    app.native_search_ms_label = label(solver_budget, f'{app.native_search_ms_var.get()} ms')
    app.native_search_ms_label.pack(side='right')
    app.native_search_ms_scale = tk.Scale(
        solver_budget, from_=0, to=2000, resolution=25, showvalue=False,
        variable=app.native_search_ms_var, orient='horizontal', command=app._on_native_solver_change,
        bg=SURFACE, fg=app.FG, troughcolor=BORDER, highlightthickness=0, bd=0,
    )
    app.native_search_ms_scale.pack(side='right', fill='x', expand=True, padx=12)
    window=section(win,'Window & performance')
    window.pack(fill='x',pady=(0,12))
    opacity=row(window)
    label(opacity,'Opacity').pack(side='left')
    app.opacity_var=tk.IntVar(value=app._window_opacity)
    app.opacity_scale=tk.Scale(opacity,from_=25,to=100,orient='horizontal',variable=app.opacity_var,
        command=app._on_opacity_change,bg=SURFACE,fg=app.FG,troughcolor=BORDER,highlightthickness=0,bd=0)
    app.opacity_scale.pack(side='left',fill='x',expand=True,padx=12)
    app.sleep_var=tk.BooleanVar(value=False)
    app.sleep_check=ttk.Checkbutton(window,text='Sleep mode \u00b7 reduce background scanning',variable=app.sleep_var,command=app._toggle_sleep_mode)
    app.sleep_check.pack(anchor='w')
    app.sound_var=tk.BooleanVar(value=app._sound_enabled)
    app.sound_check=ttk.Checkbutton(window,text='Sound notification on new hand',variable=app.sound_var,command=app._on_sound_change)
    app.sound_check.pack(anchor='w')
    app.show_confidence_var=tk.BooleanVar(value=app._show_confidence)
    app.show_confidence_check=ttk.Checkbutton(window,text='Show confidence percentages',variable=app.show_confidence_var,command=app._on_confidence_change)
    app.show_confidence_check.pack(anchor='w')
    app.tray_var=app.compact.on_minimise
    app.tray_var.set(bool(app._minimize_to_tray))
    app.tray_check=ttk.Checkbutton(window,text='Keep compact guidance when minimised',variable=app.tray_var,command=app._on_tray_change)
    app.tray_check.pack(anchor='w')
    autonomy = section(win, 'Autonomous actions')
    autonomy.pack(fill='x', pady=(0, 12))
    delay_row = row(autonomy)
    label(delay_row, 'Min delay (s)').pack(side='left', padx=(0, 6))
    app.min_delay_var = tk.StringVar(value=str(app._config.get('auto_min_delay', 0.8)))
    app.min_delay_entry = entry(delay_row, 6)
    app.min_delay_entry.configure(textvariable=app.min_delay_var)
    app.min_delay_entry.pack(side='left', padx=(0, 14))
    app.min_delay_entry.bind('<FocusOut>', app._on_autonomy_settings_change)
    app.min_delay_entry.bind('<Return>', app._on_autonomy_settings_change)
    label(delay_row, 'Max delay (s)').pack(side='left', padx=(0, 6))
    app.max_delay_var = tk.StringVar(value=str(app._config.get('auto_max_delay', 2.6)))
    app.max_delay_entry = entry(delay_row, 6)
    app.max_delay_entry.configure(textvariable=app.max_delay_var)
    app.max_delay_entry.pack(side='left')
    app.max_delay_entry.bind('<FocusOut>', app._on_autonomy_settings_change)
    app.max_delay_entry.bind('<Return>', app._on_autonomy_settings_change)
    app.enter_bet_sizing_var = tk.BooleanVar(value=bool(app._config.get('auto_enter_bet_sizing', True)))
    app.enter_bet_sizing_check = ttk.Checkbutton(
        autonomy,
        text='Type bet/raise sizing before clicking Raise',
        variable=app.enter_bet_sizing_var,
        command=app._on_autonomy_settings_change,
    )
    app.enter_bet_sizing_check.pack(anchor='w', pady=(6, 0))
    app.dry_run_var = tk.BooleanVar(value=bool(app._config.get('auto_dry_run', False)))
    app.dry_run_check = ttk.Checkbutton(
        autonomy,
        text='Dry-run mode (simulate without clicking)',
        variable=app.dry_run_var,
        command=app._on_autonomy_settings_change,
    )
    app.dry_run_check.pack(anchor='w', pady=(2, 0))
    detection=section(win,'Detection details')
    detection.pack(fill='x')
    app.last_hand_frame=row(detection)
    app.last_hand_label=label(app.last_hand_frame,'Last Hand: --')
    app.last_hand_label.pack(side='left')
    app.position_frame=row(detection)
    app.position_label=label(app.position_frame,'Position: unknown')
    app.position_label.pack(side='left')
    app.card_preview=label(detection,'')
    app.card_preview.pack(anchor='w')
    app.debug_board_btn=ttk.Button(detection,text='Debug board capture',command=app._debug_board_detection)
    app.debug_board_btn.pack(anchor='w',pady=(8,0))
    ttk.Button(win,text='Done',command=app._close_settings).pack(anchor='e',pady=(12,0))


def render_cards(app):
    """Only display suit symbols when exact cards are known."""
    cards = app._exact_cards
    if not cards and app.mode == 'postflop':
        raw=app.hand_entry.get().replace(' ','')
        if len(raw)==4 and all(raw[i].upper() in ranges.RANKS and raw[i+1].lower() in 'shdc' for i in (0,2)):
            cards=(raw[:2],raw[2:])
    ranks = app.hand[:2] if app.hand else ''
    for i,tile in enumerate(app.card_tiles):
        if cards:
            rank,suit=cards[i][0].upper(),cards[i][1].lower()
            tile.configure(text=rank.replace('T','10')+'\n'+dict(s='♠',h='♥',d='♦',c='♣')[suit],
                           bg='#f8fafc',fg='#dc2626' if suit in 'hd' else '#0f172a',
                           highlightbackground='#e2e8f0', highlightthickness=1)
        elif len(ranks)==2:
            tile.configure(text=ranks[i].replace('T','10'),bg='#f8fafc',fg='#0f172a',
                           highlightbackground='#e2e8f0', highlightthickness=1)
        else:
            tile.configure(text='\u2014',bg='#1e2d42',fg='#4a5a72',
                           highlightbackground=BORDER, highlightthickness=1)
    app.hand_hint.configure(text='e.g. Ah Kd \u00b7 exact suits' if app.mode=='postflop' else 'e.g. AKs, JJ, T9o')
