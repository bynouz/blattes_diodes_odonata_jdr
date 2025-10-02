#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tirage de Blattes — mini interface Tkinter (avec couleurs + tri)
Fichier : tirage_blattes.py

Règles / rappel :
- Config par R, V, B (≥1). Contraintes automatiques :
  Noir = Rouge ; Blanc = Vert + Bleu ; Total = 2 * (R + V + B).
- Tirages :
  diff = 0  -> 1 blatte.
  diff = +1 -> 1 blatte, possibilité de repiocher une seule fois ; 2e résultat final.
  diff = -1 -> 1 blatte, l’adversaire peut forcer une repioche unique ; 2e résultat final.
  |diff| >= 2 -> |diff| blattes SANS remise (liste affichée). Choix oral.
- Réinitialisation du sachet entre chaque test.
- Affichage : on montre uniquement les couleurs (interprétation au contexte).

Nouveautés :
- Les noms de couleurs dans les résultats sont colorés.
- Pour un tirage multiple, la liste est triée : Rouge → Vert → Bleu → Blanc → Noir.
"""

import random
import tkinter as tk
from tkinter import ttk, messagebox

# Ordre d'affichage/voulut (aussi utilisé pour trier)
COLOR_ORDER = ["Rouge", "Vert", "Bleu", "Blanc", "Noir"]
SORT_INDEX = {c: i for i, c in enumerate(COLOR_ORDER)}

def construire_sachet(r: int, v: int, b: int):
    """Construit la liste des blattes (couleurs) selon R, V, B et contraintes :
    Noir = Rouge ; Blanc = Vert + Bleu ; Total = 2*(R+V+B)
    """
    if min(r, v, b) < 1:
        raise ValueError("R, V et B doivent être des entiers ≥ 1.")
    n = r
    w = v + b
    sachet = []
    sachet += ["Rouge"] * r
    sachet += ["Noir"]  * n
    sachet += ["Blanc"] * w
    sachet += ["Vert"]  * v
    sachet += ["Bleu"]  * b
    return sachet, n, w

class TirageBlattesApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tirage de Blattes")
        self.geometry("1024x580")
        self.minsize(700, 540)

        # Valeurs de base officielles (total 30)
        self.var_r = tk.IntVar(value=3)  # Rouge
        self.var_v = tk.IntVar(value=6)  # Vert
        self.var_b = tk.IntVar(value=6)  # Bleu
        self.var_n = tk.IntVar(value=3)   # Noir (dérivé)
        self.var_w = tk.IntVar(value=12)  # Blanc (dérivé)
        self.var_total = tk.IntVar(value=30)

        # Paramètres de test
        self.var_diff_radio = tk.IntVar(value=0)     # -3..3
        self.var_diff_autre = tk.StringVar(value="") # champ "Autre (entier)"

        # État +1 / -1
        self._mode_plus_moins_un = False
        self._premier_resultat = None  # str

        self._build_ui()
        self._recalculer_derives()  # init

    # ---------- UI ----------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 8}

        # Config sachet
        frame_cfg = ttk.LabelFrame(self, text="Configuration du sachet")
        frame_cfg.pack(fill="x", **pad)

        self._add_spin(frame_cfg, "Rouge (R)", self.var_r, 1, 999, self._on_cfg_change, 0, 0)
        self._add_spin(frame_cfg, "Vert (V)",  self.var_v, 1, 999, self._on_cfg_change, 0, 1)
        self._add_spin(frame_cfg, "Bleu (B)",  self.var_b, 1, 999, self._on_cfg_change, 0, 2)

        ttk.Label(frame_cfg, text="Noir (N = R)").grid(row=1, column=0, sticky="w")
        ttk.Label(frame_cfg, textvariable=self.var_n, width=7).grid(row=1, column=0, sticky="e", padx=(0, 30))

        ttk.Label(frame_cfg, text="Blanc (W = V + B)").grid(row=1, column=1, sticky="w")
        ttk.Label(frame_cfg, textvariable=self.var_w, width=7).grid(row=1, column=1, sticky="e", padx=(0, 30))

        ttk.Label(frame_cfg, text="Total blattes").grid(row=1, column=2, sticky="w")
        ttk.Label(frame_cfg, textvariable=self.var_total, width=7).grid(row=1, column=2, sticky="e")

        ttk.Separator(self).pack(fill="x", padx=10, pady=(4, 8))

        # Choix du test
        frame_test = ttk.LabelFrame(self, text="Quel test veux-tu faire ?")
        frame_test.pack(fill="x", **pad)

        radios = ttk.Frame(frame_test)
        radios.grid(row=0, column=0, sticky="w", padx=(0, 20))
        for i, val in enumerate([-3, -2, -1, 0, 1, 2, 3]):
            ttk.Radiobutton(radios, text=str(val), value=val, variable=self.var_diff_radio)\
                .grid(row=0, column=i, padx=4, pady=4)

        other = ttk.Frame(frame_test)
        other.grid(row=0, column=1, sticky="w")
        ttk.Label(other, text="Autre (entier)").pack(side="left")
        self.entry_autre = ttk.Entry(other, width=10, textvariable=self.var_diff_autre)
        self.entry_autre.pack(side="left", padx=6)

        btns = ttk.Frame(frame_test)
        btns.grid(row=0, column=2, sticky="e")
        self.btn_tirer = ttk.Button(btns, text="Tirer", command=self._on_tirer)
        self.btn_tirer.pack(side="left", padx=4)
        self.btn_garder = ttk.Button(btns, text="Garder", command=self._on_garder)
        self.btn_repiocher = ttk.Button(btns, text="Repiocher (résultat final)", command=self._on_repiocher)
        self._set_plus_moins_un_mode(False)

        # Résultats (Text avec tags couleur)
        frame_res = ttk.LabelFrame(self, text="Résultats")
        frame_res.pack(fill="both", expand=True, **pad)
        self.txt = tk.Text(frame_res, height=12, wrap="word", state="disabled")
        self.txt.pack(fill="both", expand=True, padx=8, pady=8)

        # Tags couleurs pour le Text
        self._init_text_tags()

        # Probabilités exactes (tirage simple)
        frame_stats = ttk.LabelFrame(self, text="Probabilités (tirage simple)")
        frame_stats.pack(fill="x", **pad)
        ttk.Button(frame_stats, text="Montrer probabilités exactes", command=self._on_show_probs)\
            .pack(side="left", padx=6, pady=6)
        self.lbl_probs = ttk.Label(frame_stats, text="")
        self.lbl_probs.pack(side="left", padx=10)

        # Police un peu plus grande (optionnel)
        try:
            from tkinter import font as tkfont
            tkfont.nametofont("TkDefaultFont").configure(size=10)
        except Exception:
            pass

    def _add_spin(self, parent, label, var, frm, to, cmd, r, c):
        box = ttk.Frame(parent)
        box.grid(row=r, column=c, sticky="w", padx=(0, 30))
        ttk.Label(box, text=label).pack(side="left")
        sb = ttk.Spinbox(box, from_=frm, to=to, textvariable=var, width=7,
                         command=cmd, justify="center")
        sb.pack(side="left", padx=6)
        var.trace_add("write", lambda *_: self._on_cfg_change())

    # ---------- couleurs & logs ----------
    def _init_text_tags(self):
        """Définit les tags de couleur pour l'affichage dans le Text."""
        # Teintes lisibles sur fond clair
        self.txt.tag_config("Rouge", foreground="#d32f2f")
        self.txt.tag_config("Vert",  foreground="#2e7d32")
        self.txt.tag_config("Bleu",  foreground="#1565c0")
        self.txt.tag_config("Blanc", foreground="#616161")   # gris pour rester lisible
        self.txt.tag_config("Noir",  foreground="#000000")
        self.txt.tag_config("bold",  font=("TkDefaultFont", 10, "bold"))

    def _log_parts(self, parts):
        """Insère une liste de (texte, tag_ou_None) et ajoute un saut de ligne."""
        self.txt.config(state="normal")
        for text, tag in parts:
            if tag:
                self.txt.insert("end", text, tag)
            else:
                self.txt.insert("end", text)
        self.txt.insert("end", "\n")
        self.txt.see("end")
        self.txt.config(state="disabled")

    def _log_plain(self, text):
        self._log_parts([(text, None)])

    def _log_color_line(self, prefix, colors, suffix=""):
        """Affiche 'prefix' puis la liste triée des couleurs (taguées), puis 'suffix'."""
        sorted_colors = sorted(colors, key=lambda c: SORT_INDEX.get(c, 999))
        parts = []
        if prefix:
            parts.append((prefix, None))
        for i, c in enumerate(sorted_colors):
            if i > 0:
                parts.append((", ", None))
            parts.append((c, c if c in SORT_INDEX else None))  # tag = nom de couleur
        if suffix:
            parts.append((suffix, None))
        self._log_parts(parts)

    # ---------- callbacks ----------
    def _on_cfg_change(self):
        try:
            self._recalculer_derives()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _recalculer_derives(self):
        r = int(self.var_r.get())
        v = int(self.var_v.get())
        b = int(self.var_b.get())
        if min(r, v, b) < 1:
            r = max(1, r); v = max(1, v); b = max(1, b)
            self.var_r.set(r); self.var_v.set(v); self.var_b.set(b)
        sachet, n, w = construire_sachet(r, v, b)
        self.var_n.set(n)
        self.var_w.set(w)
        self.var_total.set(len(sachet))

    def _resolve_diff(self):
        txt = self.var_diff_autre.get().strip()
        if txt != "":
            try:
                return int(txt)
            except ValueError:
                raise ValueError("« Autre (entier) » doit être un entier (ex : -7, 0, 5).")
        return int(self.var_diff_radio.get())

    def _on_tirer(self):
        if self._mode_plus_moins_un:
            messagebox.showwarning("Tirage en cours", "Terminez d'abord (Garder ou Repiocher).")
            return

        try:
            diff = self._resolve_diff()
        except Exception as e:
            messagebox.showerror("Entrée invalide", str(e))
            return

        # Sachet (réinitialisé à chaque test)
        try:
            sachet, _, _ = construire_sachet(self.var_r.get(), self.var_v.get(), self.var_b.get())
        except Exception as e:
            messagebox.showerror("Configuration invalide", str(e))
            return

        total = len(sachet)

        if diff == 0:
            c = random.choice(sachet)
            self._log_color_line("Tirage (0) → ", [c])
            return

        if diff in (+1, -1):
            self._premier_resultat = random.choice(sachet)
            self._set_plus_moins_un_mode(True)
            self._log_color_line(f"Tirage ({diff:+d}) → ", [self._premier_resultat],
                                 "  (Vous pouvez garder ou repiocher une fois)")
            return

        # |diff| >= 2 : tirage sans remise
        n_draws = abs(diff)
        if n_draws > total:
            messagebox.showerror(
                "Tirage impossible",
                f"Vous demandez {n_draws} blattes mais le sachet ne contient que {total}. "
                f"Réduisez la demande ou augmentez la configuration."
            )
            return

        tirage = random.sample(sachet, k=n_draws)  # sans remise
        self._log_color_line(f"Tirage ({diff:+d}) sans remise → ", tirage,
                             f"\n(Choix oral : {'joueur' if diff > 0 else 'adversaire/Deus'})")

    def _on_garder(self):
        if not self._mode_plus_moins_un or self._premier_resultat is None:
            return
        self._log_color_line("Décision : garder → ", [self._premier_resultat])
        self._set_plus_moins_un_mode(False)
        self._premier_resultat = None

    def _on_repiocher(self):
        if not self._mode_plus_moins_un:
            return
        try:
            sachet, _, _ = construire_sachet(self.var_r.get(), self.var_v.get(), self.var_b.get())
        except Exception as e:
            messagebox.showerror("Configuration invalide", str(e))
            return
        c = random.choice(sachet)
        self._log_color_line("Décision : repiocher → ", [c], " (résultat final)")
        self._set_plus_moins_un_mode(False)
        self._premier_resultat = None

    def _on_show_probs(self):
        """Affiche les probabilités exactes d'un tirage simple (1 blatte)."""
        try:
            sachet, _, _ = construire_sachet(self.var_r.get(), self.var_v.get(), self.var_b.get())
        except Exception as e:
            messagebox.showerror("Configuration invalide", str(e))
            return
        total = len(sachet)
        counts = {c: 0 for c in COLOR_ORDER}
        for c in sachet:
            counts[c] += 1
        parts = [f"{c}: {counts[c]}/{total} = {counts[c]*100.0/total:.2f}%" for c in COLOR_ORDER]
        self.lbl_probs.config(text="  |  ".join(parts))

    def _set_plus_moins_un_mode(self, active: bool):
        self._mode_plus_moins_un = active
        if active:
            self.btn_tirer.config(state="disabled")
            self.btn_garder.pack(side="left", padx=4)
            self.btn_repiocher.pack(side="left", padx=4)
        else:
            self.btn_garder.pack_forget()
            self.btn_repiocher.pack_forget()
            self.btn_tirer.config(state="normal")

def main():
    app = TirageBlattesApp()
    app.mainloop()

if __name__ == "__main__":
    main()
