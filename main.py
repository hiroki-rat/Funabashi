import contextlib
import datetime
import importlib
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import traceback
import winreg

# ==============================================================================
# 基盤システム: ライブラリの自動検出 & インストールダイアログ
# ==============================================================================
class StartupCheckDialog(tk.Toplevel):
    def __init__(self, parent, missing_pkgs: dict):
        super().__init__(parent)
        self.title("環境・依存関係の確認")
        self.geometry("480x260")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.transient(parent)

        self.update_idletasks()
        self.grab_set()

        self.proceed = False
        self.missing_pkgs = missing_pkgs  # {"import名": "pip名"} の辞書

        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(
            main_frame,
            text="⚠️ 必要なライブラリが見つかりません",
            font=("", 11, "bold"),
            foreground="red",
        ).pack(anchor="w", pady=(0, 10))

        text_area = tk.Text(main_frame, wrap="word", height=5)
        text_area.pack(fill="both", expand=True, pady=5)

        info_msg = (
            "以下のPythonライブラリが不足しています:\n・ "
            + "\n・ ".join(self.missing_pkgs.values())
            + "\n\n「Pythonライブラリ自動インストール」を実行してください。"
        )

        text_area.insert("1.0", info_msg)
        text_area.config(state="disabled")

        btn_box = ttk.Frame(main_frame)
        btn_box.pack(fill="x", pady=(10, 0))

        self.btn_install = ttk.Button(
            btn_box,
            text="🚀 Pythonライブラリ自動インストール",
            command=self._install,
        )
        self.btn_install.pack(side="left")

        self.btn_ignore = ttk.Button(btn_box, text="無視して続ける", command=self._continue)
        self.btn_ignore.pack(side="right", padx=5)

        self.btn_cancel_dialog = ttk.Button(btn_box, text="中止", command=self._cancel)
        self.btn_cancel_dialog.pack(side="right")

    def _install(self):
        self.btn_install.config(state="disabled", text="インストール中...")
        self.btn_ignore.config(state="disabled")
        self.btn_cancel_dialog.config(state="disabled")

        def run_install():
            pip_names = list(self.missing_pkgs.values())
            cmd = [sys.executable, "-m", "pip", "install"] + pip_names
            try:
                subprocess.run(cmd, check=True)
                self.after(0, self._install_success)
            except Exception as e:
                self.after(0, lambda err=e: self._install_fail(err))

        threading.Thread(target=run_install, daemon=True).start()

    def _install_success(self):
        messagebox.showinfo("完了", "ライブラリのインストールが完了しました。", parent=self)
        self.proceed = True
        self.destroy()

    def _install_fail(self, e):
        messagebox.showerror("エラー", f"インストール失敗:\n{e}", parent=self)
        self.btn_install.config(state="normal", text="🚀 Pythonライブラリ自動インストール")
        self.btn_ignore.config(state="normal")
        self.btn_cancel_dialog.config(state="normal")

    def _continue(self):
        self.proceed = True
        self.destroy()

    def _cancel(self):
        self.proceed = False
        self.destroy()

def check_and_install_libraries(root):
    """起動時に必要なライブラリをチェックする"""
    required_libs = {"selenium": "selenium"}
    missing_pkgs = {}
    for import_name, pip_name in required_libs.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing_pkgs[import_name] = pip_name

    if missing_pkgs:
        dialog = StartupCheckDialog(root, missing_pkgs)
        root.wait_window(dialog)
        if not dialog.proceed:
            sys.exit(0)

# ==========================================
# これより下は必要なライブラリ（selenium等）が揃っている前提でインポート
# ==========================================
try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        NoAlertPresentException,
        TimeoutException,
        UnexpectedAlertPresentException,
    )
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.select import Select
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    pass

# ==========================================
# 定数・マスタデータ定義
# ==========================================
BASE_URL = "https://funayoyaku.city.funabashi.chiba.jp/web/"

SUB_FACILITIES = {
    "行田運動広場": ["運動広場（Ａ面）", "運動広場（全面）", "運動広場（Ｂ面）"],
    "若松公園": ["野球場（Ａ面）", "野球場（Ｂ面）"],
    "高瀬町まちかどスポーツ広場": [
        "野球場",
        "少年野球場（Ａ面）",
        "少年野球場（Ｃ面）",
        "少年野球場（Ｄ面）",
    ],
    "豊富まちかどスポーツ広場": ["少年野球場（Ａ面）", "少年野球場（Ｂ面）"],
}

ALL_GROUNDS = [
    "行田運動広場",
    "運動公園",
    "若松公園",
    "法典公園（グラスポ）",
    "高瀬町まちかどスポーツ広場",
    "豊富まちかどスポーツ広場",
    "藤原まちかどスポーツ広場",
    "大神保町まちかどスポーツ広場",
    "ふなばし三番瀬海浜公園",
]

GROUND_COMBO_WIDTH = max(len(name) for name in ALL_GROUNDS) * 2
SUB_FACILITY_COMBO_WIDTH = max(
    len(name) for names in SUB_FACILITIES.values() for name in names
) * 2

GROUND_TIME_SLOTS = {
    "行田運動広場": {
        "8:30〜10:30": ("830", "1030"),
        "10:30〜12:30": ("1030", "1230"),
        "12:30〜14:30": ("1230", "1430"),
        "14:30〜16:30": ("1430", "1630"),
        "16:30〜18:30": ("1630", "1830"),
    },
    "運動公園": {
        "7:00〜9:00": ("700", "900"),
        "9:00〜11:00": ("900", "1100"),
        "11:00〜13:00": ("1100", "1300"),
        "13:00〜15:00": ("1300", "1500"),
        "15:00〜17:00": ("1500", "1700"),
        "17:00〜19:00": ("1700", "1900"),
        "19:00〜21:00": ("1900", "2100"),
    },
    "若松公園": {
        "6:30〜8:30": ("630", "830"),
        "8:30〜10:30": ("830", "1030"),
        "10:30〜12:30": ("1030", "1230"),
        "12:30〜14:30": ("1230", "1430"),
        "14:30〜16:30": ("1430", "1630"),
        "16:30〜18:30": ("1630", "1830"),
    },
    "法典公園（グラスポ）": {
        "9:00〜11:00": ("900", "1100"),
        "11:00〜13:00": ("1100", "1300"),
        "13:00〜15:00": ("1300", "1500"),
        "15:00〜17:00": ("1500", "1700"),
    },
    "高瀬町まちかどスポーツ広場": {
        "6:30〜8:30": ("630", "830"),
        "8:30〜10:30": ("830", "1030"),
        "10:30〜12:30": ("1030", "1230"),
        "12:30〜14:30": ("1230", "1430"),
        "14:30〜16:30": ("1430", "1630"),
        "16:30〜18:30": ("1630", "1830"),
    },
    "豊富まちかどスポーツ広場": {
        "8:30〜10:30": ("830", "1030"),
        "10:30〜12:30": ("1030", "1230"),
        "12:30〜14:30": ("1230", "1430"),
        "14:30〜16:30": ("1430", "1630"),
    },
    "藤原まちかどスポーツ広場": {
        "9:00〜11:00": ("900", "1100"),
        "11:00〜13:00": ("1100", "1300"),
        "13:00〜15:00": ("1500", "1700"),
    },
    "大神保町まちかどスポーツ広場": {
        "8:30〜10:30": ("830", "1030"),
        "10:30〜12:30": ("1030", "1230"),
        "12:30〜14:30": ("1230", "1430"),
        "14:30〜16:30": ("1430", "1630"),
    },
    "ふなばし三番瀬海浜公園": {
        "9:00〜11:00": ("900", "1100"),
        "11:00〜13:00": ("1100", "1300"),
        "13:00〜15:00": ("1300", "1500"),
        "15:00〜17:00": ("1500", "1700"),
    },
}

TODAY = datetime.date.today()
# 起動年から100年先まで選べるようにし、毎年の起動時に候補を更新する。
YEAR_OPTIONS = [str(y) for y in range(TODAY.year, TODAY.year + 101)]
MONTH_OPTIONS = [str(m).zfill(2) for m in range(1, 13)]
DAY_OPTIONS = [str(d).zfill(2) for d in range(1, 32)]

# 抽選申し込みの初期値は翌々月1日。
_def_month = TODAY.month + 2
_def_year = TODAY.year
if _def_month > 12:
    _def_month -= 12
    _def_year += 1

DEFAULT_YEAR_STR = str(_def_year)
DEFAULT_MONTH_STR = str(_def_month).zfill(2)
DEFAULT_DAY_STR = "01"

# 利用者差し替えの初期値は翌月1日（抽選申し込みとは独立）。
_replace_def_month = TODAY.month + 1
_replace_def_year = TODAY.year
if _replace_def_month > 12:
    _replace_def_month -= 12
    _replace_def_year += 1

REPLACE_DEFAULT_YEAR_STR = str(_replace_def_year)
REPLACE_DEFAULT_MONTH_STR = str(_replace_def_month).zfill(2)
REPLACE_DEFAULT_DAY_STR = "01"


def get_real_desktop_path() -> str:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        )
        path, _ = winreg.QueryValueEx(key, "Desktop")
        return os.path.expandvars(path)
    except Exception:
        user_home = os.path.expanduser("~")
        for sub_dir in [
            os.path.join("OneDrive", "Desktop"),
            os.path.join("OneDrive", "デスクトップ"),
            "Desktop",
        ]:
            full_path = os.path.join(user_home, sub_dir)
            if os.path.exists(full_path):
                return full_path
        return os.path.join(user_home, "Desktop")


def clean_exception_msg(e: Exception) -> str:
    msg = str(e).split("\n")[0]
    if "Stacktrace:" in msg or "msedgedriver" in msg:
        return "画面要素の読み込みに失敗したか、ブラウザ通信が中断されました。"
    return msg


# ==========================================
# Selenium 自動化クラス (操作エンジン)
# ==========================================
class FunabashiBot:
    def __init__(
        self,
        driver,
        log_func,
        output_folder: str = "",
        stop_checker=None,
        slow_mode: bool = False,
        zoom: str = "67%",
    ):
        self.driver = driver
        self.slow_mode = slow_mode
        self.zoom = zoom
        self.log = log_func
        self.output_folder = output_folder
        self.is_stopped = stop_checker if stop_checker else (lambda: False)

        base_wait_time = 20 if self.slow_mode else 10
        self.wait = WebDriverWait(driver, base_wait_time)

    def _check_stop(self):
        if self.is_stopped():
            raise InterruptedError("ユーザーによって処理が中止されました。")

    def _click_with_retry(self, by: By, selector: str, retries: int = 3, wait_for_stale: bool = True):
        self._check_stop()
        retry_wait = 1.0 if self.slow_mode else 0.5
        for i in range(retries):
            try:
                element = self.wait.until(EC.element_to_be_clickable((by, selector)))
                element.click()
                if wait_for_stale:
                    with contextlib.suppress(Exception):
                        WebDriverWait(self.driver, 1.5).until(EC.staleness_of(element))
                return
            except Exception as e:
                if i == retries - 1:
                    raise e
                time.sleep(retry_wait)

    def _input_with_retry(self, by: By, selector: str, keys: str, retries: int = 3):
        self._check_stop()
        retry_wait = 1.0 if self.slow_mode else 0.5
        for i in range(retries):
            try:
                element = self.wait.until(EC.presence_of_element_located((by, selector)))
                element.clear()
                element.send_keys(keys)
                return
            except Exception as e:
                if i == retries - 1:
                    raise e
                time.sleep(retry_wait)

    def click_image_by_alt(self, alt_text: str, extra_xpath: str = ""):
        xpath = f"//img[@alt='{alt_text}' {extra_xpath}]" if extra_xpath else f"//img[@alt='{alt_text}']"
        self._click_with_retry(By.XPATH, xpath)

    def take_screenshot(self, id_index: int, user_id: str, suffix: str, wait_sec: float = 0.5, zoom: str = None):
        if not self.output_folder:
            return

        actual_wait = wait_sec * 2 if self.slow_mode else wait_sec
        time.sleep(actual_wait)

        target_zoom = zoom if zoom is not None else self.zoom
        if target_zoom:
            with contextlib.suppress(Exception):
                zoom_val = target_zoom.replace("%", "").strip()
                self.driver.execute_script(f"document.body.style.zoom='{zoom_val}%';")
                time.sleep(0.3)

        filename = f"{id_index:03d}_{user_id}_{suffix}.png"
        filepath = os.path.join(self.output_folder, filename)
        try:
            self.driver.save_screenshot(filepath)
            self.log(f"    📸 スクショ保存完了: {filename}")
        except Exception as e:
            self.log(f"    ⚠️ スクショ保存エラー: {e}")

    def login(self, user_id: str, password: str):
        self.log(f"🔑 ID: {user_id} でログイン中...")
        self.driver.get(BASE_URL)
        self._input_with_retry(By.CSS_SELECTOR, "#userId", user_id)
        self._input_with_retry(By.CSS_SELECTOR, "#password", password)
        self.click_image_by_alt("ログイン")

    def logout(self, user_id: str):
        for _ in range(2):
            try:
                btns = self.driver.find_elements(
                    By.XPATH, "//img[@alt='終了' or contains(@src, 'bw_end') or @alt='メニューへ' or contains(@src, 'bw_menu')]"
                )
                if btns:
                    for b in btns:
                        if b.is_displayed():
                            b.click()
                            time.sleep(0.3)
                            break
                else:
                    break
            except Exception:
                break
        self.log(f"    🚪 {user_id} ログアウト完了")

    def navigate_to_ground_select(self):
        try:
            self.click_image_by_alt("抽選の申込み")
        except Exception:
            raise Exception("ログインに失敗したか、メニュー画面に移動できませんでした。（ID/PWをご確認ください）")

        self.click_image_by_alt("利用目的から")
        self._click_with_retry(By.XPATH, "//a[contains(text(), '軟式少年野球') or contains(text(), '軟式野球')]")
        self.click_image_by_alt("申込みの選択")
        
    def navigate_to_replace_new_search(self, ground_name: str, target_date: str):
        """【利用者差し替え用】差し替え後（Chrome）の画面遷移"""
        self.click_image_by_alt("予約の申込み")
        self.click_image_by_alt("複合検索条件")
        self.click_image_by_alt("利用目的の選択")
        self._click_with_retry(By.LINK_TEXT, "軟式野球")
        self.click_image_by_alt("館の選択")
        # 部分一致でグラウンドを選択（表記ゆれにも対応）
        self._click_with_retry(By.PARTIAL_LINK_TEXT, ground_name)
        self.select_replace_search_date(target_date)
        self.click_image_by_alt("検索を開始する")

    def navigate_to_replace_old_cancel(self):
        """利用者差し替え用に、差し替え前アカウントの予約取消画面を開く。"""
        self.click_image_by_alt("予約の取消")

    def select_replace_search_date(self, target_date: str):
        """利用者差し替え用の施設空き状況検索画面で年月日を設定する。"""
        year, month, day = target_date[:4], target_date[4:6], target_date[6:8]
        date_select_xpath = (
            "//*[self::td or self::th][normalize-space()='年月日']"
            "/following-sibling::*[1]//select"
        )

        try:
            date_selects = WebDriverWait(self.driver, 10).until(
                lambda driver: driver.find_elements(By.XPATH, date_select_xpath)
            )
            if len(date_selects) < 3:
                raise ValueError("年月日プルダウンが見つかりませんでした。")

            for dropdown, value in zip(date_selects[:3], (year, month, day)):
                select = Select(dropdown)
                candidate_values = (value, str(int(value)))
                for candidate in candidate_values:
                    try:
                        select.select_by_value(candidate)
                        break
                    except Exception:
                        try:
                            select.select_by_visible_text(candidate)
                            break
                        except Exception:
                            continue
                else:
                    raise ValueError(f"日付の選択肢「{value}」が見つかりませんでした。")
        except Exception as e:
            raise Exception(f"検索画面で日付 {year}年{month}月{day}日 を設定できませんでした。") from e

    def select_ground(self, ground_name: str, sub_facility: str):
        self._click_with_retry(By.LINK_TEXT, ground_name)
        if sub_facility and sub_facility != "※詳細指定なし":
            self._click_with_retry(By.LINK_TEXT, sub_facility)

    def select_date_and_time(self, target_date: str, start_code: str, end_code: str):
        day_num = int(target_date[6:8])
        next_week_clicks = (day_num - 1) // 7

        for _ in range(next_week_clicks):
            self.click_image_by_alt("次の週", extra_xpath="or contains(@src, 'bw_nextweeks')")

        xpath = (
            f"//a[contains(@href, '{target_date}') "
            f"and contains(@href, ', {start_code},') "
            f"and contains(@href, ', {end_code},')]"
        )

        try:
            self._click_with_retry(By.XPATH, xpath)
        except Exception:
            raise Exception(f"日付:{target_date} の時間帯コマ（{start_code}〜）が選択不可（×印または受付外）です。")

        self.click_image_by_alt("申込み")

    def submit_final_application(self, request_index: int, num_people: str = "40", user_id: str = "", id_index: int = 1) -> bool:
        self._input_with_retry(By.CSS_SELECTOR, "#applyPepopleNum", num_people)

        target_btn_xpath = f"//input[@value='申込み' and contains(@onclick, ', {request_index},')]"
        try:
            self._click_with_retry(By.XPATH, target_btn_xpath, wait_for_stale=False)
        except Exception:
            self._click_with_retry(By.XPATH, f"(//input[@value='申込み'])[{request_index}]", wait_for_stale=False)

        with contextlib.suppress(TimeoutException, NoAlertPresentException, UnexpectedAlertPresentException):
            WebDriverWait(self.driver, 2).until(EC.alert_is_present())
            self.driver.switch_to.alert.accept()

        time.sleep(0.5)

        if request_index == 4:
            self.take_screenshot(id_index, user_id, "申し込み", wait_sec=0.5)

        pressed_no_mail = False
        with contextlib.suppress(Exception):
            no_mail_btns = self.driver.find_elements(
                By.XPATH, "//img[@alt='送信しない' or contains(@src, 'bw_notransmitmail')]"
            )
            for btn in no_mail_btns:
                if btn.is_displayed():
                    btn.click()
                    pressed_no_mail = True
                    time.sleep(0.5)
                    break

        return pressed_no_mail

    def finish_request_and_continue(self, is_last_request: bool, user_id: str, pressed_no_mail: bool):
        if is_last_request:
            self.logout(user_id)
        else:
            if pressed_no_mail:
                self.click_image_by_alt("メニューへ", extra_xpath="or contains(@src, 'bw_menu')")
            else:
                self.click_image_by_alt("終了", extra_xpath="or contains(@src, 'bw_end')")
                self.click_image_by_alt("メニューへ", extra_xpath="or contains(@src, 'bw_menu')")

    def confirm_win_if_present(self):
        try:
            select_btns = self.driver.find_elements(
                By.XPATH, "//img[@alt='選択' or contains(@src, 'bw_selectmaru')]"
            )
            if select_btns:
                self.log("    🎉 当選を確認！確定処理を行っています...")
                for btn in select_btns:
                    with contextlib.suppress(Exception):
                        if btn.is_displayed():
                            btn.click()
                            time.sleep(0.3)

                confirm_btns = self.driver.find_elements(
                    By.XPATH, "//img[@alt='確認' or contains(@src, 'bw_lotconfirmed')]"
                )
                for btn in confirm_btns:
                    with contextlib.suppress(Exception):
                        if btn.is_displayed():
                            btn.click()
                            time.sleep(0.5)

                with contextlib.suppress(TimeoutException, NoAlertPresentException, UnexpectedAlertPresentException):
                    WebDriverWait(self.driver, 2).until(EC.alert_is_present())
                    self.driver.switch_to.alert.accept()

                time.sleep(0.5)
                with contextlib.suppress(Exception):
                    self.click_image_by_alt("終了", extra_xpath="or contains(@src, 'bw_end')")
                    time.sleep(0.5)
                    
        except Exception:
            pass

    def run_single_id_apply(self, user_id: str, password: str, requests_list: list, num_people: str, id_index: int = 1):
        self._check_stop()
        self.login(user_id, password)

        total_reqs = len(requests_list)
        for idx, req in enumerate(requests_list, start=1):
            self._check_stop()
            self.log(f"  └ 第{idx}希望 申込中: {req['ground']} ({req['date']})")

            self.navigate_to_ground_select()
            self.select_ground(req["ground"], req["sub"])
            self.select_date_and_time(req["date"], req["start"], req["end"])
            
            pressed_no_mail = self.submit_final_application(
                request_index=idx, num_people=num_people, user_id=user_id, id_index=id_index
            )

            is_last = (idx == total_reqs)
            self.finish_request_and_continue(is_last_request=is_last, user_id=user_id, pressed_no_mail=pressed_no_mail)
            self.log(f"    ✔ 第{idx}希望 申込完了")

    def run_single_id_result(self, user_id: str, password: str, id_index: int = 1):
        self._check_stop()
        self.login(user_id, password)

        try:
            self.click_image_by_alt("抽選結果の確認")
        except Exception:
            raise Exception("「抽選結果の確認」ボタンが見つかりませんでした。（ログイン失敗の可能性があります）")

        self.confirm_win_if_present()
        self.take_screenshot(id_index, user_id, "抽選結果", wait_sec=0.4)

        with contextlib.suppress(Exception):
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ENTER)

        self.logout(user_id)

    def run_single_id_cancel(self, user_id: str, password: str, id_index: int = 1):
        self._check_stop()
        self.login(user_id, password)

        try:
            self.click_image_by_alt("抽選申込みの取消")
        except Exception:
            raise Exception("「抽選申込みの取消」ボタンが見つかりませんでした。")

        select_btns = self.driver.find_elements(By.XPATH, "//img[@alt='選択' or starts-with(@name, 'gifName')]")
        if not select_btns:
            self.log("    ⚠️ 取消対象の申込みが見つかりませんでした。")
        else:
            for btn in select_btns[:4]:
                with contextlib.suppress(Exception):
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(0.3)

            self.click_image_by_alt("取消")

            with contextlib.suppress(TimeoutException, NoAlertPresentException, UnexpectedAlertPresentException):
                WebDriverWait(self.driver, 2).until(EC.alert_is_present())
                self.driver.switch_to.alert.accept()
                time.sleep(0.5)

            with contextlib.suppress(Exception):
                no_mail_btns = self.driver.find_elements(
                    By.XPATH, "//img[@alt='送信しない' or contains(@src, 'bw_notransmitmail')]"
                )
                for btn in no_mail_btns:
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(0.5)
                        break

            self.click_image_by_alt("終了", extra_xpath="or contains(@src, 'bw_end')")

        self.logout(user_id)


# ==========================================
# GUI アプリケーションクラス
# ==========================================
class FunabashiApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("船橋市施設予約 抽選申込自動化ツール")
        self.root.geometry("1000x880")

        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self.driver = None
        self.is_stopped = False
        self.stop_win = None
        self.is_running = False

        self.log_queue = queue.Queue()
        self.max_log_lines = 1000

        self.id_entries = []
        self.pw_entries = []
        self.ground_combos = []
        self.sub_combos = []
        self.year_combos = []
        self.month_combos = []
        self.day_combos = []
        self.time_combos = []

        self._build_ui()

        self.root.after(100, self._check_log_queue)

    def _build_ui(self):
        self.main_canvas = tk.Canvas(self.root, borderwidth=0, highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = tk.Frame(self.main_canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")),
        )
        self.main_window_id = self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        def _on_main_canvas_configure(event):
            self.main_canvas.itemconfig(self.main_window_id, width=event.width)
            if event.height > self.scrollable_frame.winfo_reqheight():
                self.main_canvas.itemconfig(self.main_window_id, height=event.height)
            else:
                self.main_canvas.itemconfig(self.main_window_id, height="")
                
        self.main_canvas.bind("<Configure>", _on_main_canvas_configure)

        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        self.main_scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)

        # 1. ヘッダーエリア
        frame_top_all = tk.Frame(self.scrollable_frame)
        frame_top_all.pack(pady=4, fill=tk.X, padx=15)

        frame_paste = tk.Frame(frame_top_all)
        frame_paste.pack(side=tk.LEFT)
        tk.Label(frame_paste, text="ID一括貼り付け:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.paste_entry = tk.Entry(frame_paste, width=22)
        self.paste_entry.pack(side=tk.LEFT, padx=5)
        self.paste_entry.bind("<Button-3>", self.show_paste_context_menu)
        self.paste_context_menu = tk.Menu(self.root, tearoff=False)
        self.paste_context_menu.add_command(label="貼り付け", command=self.paste_from_context_menu)
        reflect_btn = tk.Button(
            frame_paste, text="一括反映", command=self.reflect_ids, bg="#32cd32", fg="white", font=("Arial", 9, "bold")
        )
        reflect_btn.pack(side=tk.LEFT, padx=2)
        tk.Button(
            frame_paste, text="クリア", command=self.clear_paste_entry,
            bg="#6c757d", fg="white", font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=2)

        frame_sub_btns = tk.Frame(frame_top_all)
        frame_sub_btns.pack(side=tk.LEFT, padx=20)
        help_btn = tk.Button(
            frame_sub_btns, text="❓ ヘルプ", command=self.open_help_window, bg="#17a2b8", fg="white", font=("Arial", 9, "bold")
        )
        help_btn.pack(side=tk.LEFT, padx=3)

        ttk.Separator(self.scrollable_frame, orient="horizontal").pack(fill=tk.X, padx=10, pady=2)

        # 2. メイン領域 (ID情報 ＆ ログ)
        frame_main_middle = tk.Frame(self.scrollable_frame)
        frame_main_middle.pack(fill=tk.X, padx=15, pady=2)

        frame_left_ids = tk.LabelFrame(
            frame_main_middle, text="ログイン情報 (縦一覧表示)", font=("Arial", 10, "bold"), padx=5, pady=3
        )
        frame_left_ids.pack(side=tk.LEFT, anchor="n", padx=(0, 5))

        frame_id_header = tk.Frame(frame_left_ids)
        frame_id_header.pack(fill=tk.X, pady=1)
        tk.Label(frame_id_header, text="ID", font=("Arial", 9, "bold"), width=12).pack(side=tk.LEFT, padx=(20, 0))
        tk.Label(frame_id_header, text="パスワード", font=("Arial", 9, "bold"), width=10).pack(side=tk.LEFT, padx=(5, 0))
        add_btn = tk.Button(
            frame_id_header, text="＋ 行追加", command=self.add_id_row, bg="#4682b4", fg="white", font=("Arial", 8, "bold")
        )
        add_btn.pack(side=tk.RIGHT, padx=5)
        tk.Button(
            frame_id_header, text="クリア", command=self.clear_login_info,
            bg="#6c757d", fg="white", font=("Arial", 8, "bold")
        ).pack(side=tk.RIGHT, padx=2)

        id_scroll_frame = tk.Frame(frame_left_ids)
        id_scroll_frame.pack(fill=tk.BOTH, expand=True, pady=1)

        self.id_canvas = tk.Canvas(id_scroll_frame, width=270, height=155, borderwidth=0, highlightthickness=0)
        self.id_scrollbar = ttk.Scrollbar(id_scroll_frame, orient="vertical", command=self.id_canvas.yview)
        self.id_container_frame = tk.Frame(self.id_canvas)

        self.id_container_frame.bind(
            "<Configure>",
            lambda e: self.id_canvas.configure(scrollregion=self.id_canvas.bbox("all")),
        )
        self.id_window_id = self.id_canvas.create_window((0, 0), window=self.id_container_frame, anchor="nw")

        def _on_id_canvas_configure(event):
            self.id_canvas.itemconfig(self.id_window_id, width=event.width)
            self._refresh_id_scrollregion()

        self.id_canvas.bind("<Configure>", _on_id_canvas_configure)

        self.id_canvas.configure(yscrollcommand=self.id_scrollbar.set)

        self.id_scrollbar.pack(side="right", fill="y")
        self.id_canvas.pack(side="left", fill="both", expand=True)
        self.id_canvas.bind("<MouseWheel>", self._on_id_mousewheel)
        self.id_container_frame.bind("<MouseWheel>", self._on_id_mousewheel)
        self.id_scrollbar.bind("<MouseWheel>", self._on_id_mousewheel)

        self.root.bind_all("<MouseWheel>", self._on_global_mousewheel)

        for _ in range(5):
            self.add_id_row()

        frame_right_log = tk.LabelFrame(frame_main_middle, text="進捗ログ", font=("Arial", 10, "bold"), padx=8, pady=3)
        frame_right_log.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.log_text = tk.Text(frame_right_log, height=12, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        ttk.Separator(self.scrollable_frame, orient="horizontal").pack(fill=tk.X, padx=10, pady=3)

        # 3. 動作設定 枠
        frame_options = tk.LabelFrame(
            self.scrollable_frame, text="動作設定", font=("Arial", 10, "bold"), padx=15, pady=4
        )
        frame_options.pack(fill=tk.X, padx=15, pady=3)

        frame_options_row = tk.Frame(frame_options)
        frame_options_row.pack(fill=tk.X, anchor="w", pady=1)

        frame_zoom = tk.Frame(frame_options_row)
        frame_zoom.pack(side=tk.LEFT, padx=(0, 15))

        tk.Label(frame_zoom, text="スクショ拡大率:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.zoom_combo = ttk.Combobox(
            frame_zoom, values=["100%", "90%", "80%", "75%", "67%", "50%"], state="readonly", width=6
        )
        self.zoom_combo.set("67%")
        self.zoom_combo.pack(side=tk.LEFT, padx=2)

        self.headless_var = tk.BooleanVar(value=False)
        chk_headless = tk.Checkbutton(
            frame_options_row, text="ブラウザ画面を表示しない（高速化・低負荷）", variable=self.headless_var, font=("Arial", 9)
        )
        chk_headless.pack(side=tk.LEFT, padx=15)

        self.slow_mode_var = tk.BooleanVar(value=False)
        chk_slow = tk.Checkbutton(
            frame_options_row, text="ゆっくり動作させる（低スペックPC・回線が遅いとき）", variable=self.slow_mode_var, font=("Arial", 9)
        )
        chk_slow.pack(side=tk.LEFT, padx=15)

        # 4. 抽選申し込み 枠
        frame_requests = tk.LabelFrame(
            self.scrollable_frame, text="抽選申し込み", font=("Arial", 10, "bold"), padx=15, pady=5
        )
        frame_requests.pack(fill=tk.X, padx=15, pady=4)

        frame_config = tk.Frame(frame_requests)
        frame_config.pack(fill=tk.X, pady=(0, 4))
        tk.Label(frame_config, text="申込利用人数（共通）:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        self.people_combo = ttk.Combobox(
            frame_config, values=[str(n) for n in range(1, 100)], state="readonly", width=4
        )
        self.people_combo.set("40")
        self.people_combo.pack(side=tk.LEFT, padx=2)
        tk.Label(frame_config, text="人", font=("Arial", 10)).pack(side=tk.LEFT)

        for i in range(4):
            row_frame = tk.Frame(frame_requests)
            row_frame.pack(fill=tk.X, pady=1)
            tk.Label(row_frame, text=f"第{i+1}希望:", font=("Arial", 9, "bold"), width=7, anchor="w").pack(side=tk.LEFT)

            g_combo = ttk.Combobox(
                row_frame, values=ALL_GROUNDS, state="readonly", width=GROUND_COMBO_WIDTH
            )
            g_combo.set("行田運動広場")
            g_combo.pack(side=tk.LEFT, padx=2)
            self.ground_combos.append(g_combo)

            s_combo = ttk.Combobox(row_frame, state="readonly", width=SUB_FACILITY_COMBO_WIDTH)
            s_combo.pack(side=tk.LEFT, padx=2)
            self.sub_combos.append(s_combo)

            tk.Label(row_frame, text="日:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 1))

            y_combo = ttk.Combobox(row_frame, values=YEAR_OPTIONS, state="readonly", width=6)
            y_combo.set(DEFAULT_YEAR_STR)
            y_combo.pack(side=tk.LEFT, padx=1)
            self.year_combos.append(y_combo)
            tk.Label(row_frame, text="年", font=("Arial", 9)).pack(side=tk.LEFT)

            m_combo = ttk.Combobox(row_frame, values=MONTH_OPTIONS, state="readonly", width=4)
            m_combo.set(DEFAULT_MONTH_STR)
            m_combo.pack(side=tk.LEFT, padx=1)
            self.month_combos.append(m_combo)
            tk.Label(row_frame, text="月", font=("Arial", 9)).pack(side=tk.LEFT)

            d_combo = ttk.Combobox(row_frame, values=DAY_OPTIONS, state="readonly", width=4)
            d_combo.set(DEFAULT_DAY_STR)
            d_combo.pack(side=tk.LEFT, padx=1)
            self.day_combos.append(d_combo)
            tk.Label(row_frame, text="日", font=("Arial", 9)).pack(side=tk.LEFT)

            tk.Label(row_frame, text="時:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 1))
            t_combo = ttk.Combobox(row_frame, state="readonly", width=12)
            t_combo.pack(side=tk.LEFT, padx=2)
            self.time_combos.append(t_combo)

            g_combo.bind("<<ComboboxSelected>>", lambda event, idx=i: self._on_ground_combo_change(idx))
            self._on_ground_combo_change(i)

        frame_apply_btn = tk.Frame(frame_requests)
        frame_apply_btn.pack(pady=(6, 3))

        self.submit_btn = tk.Button(
            frame_apply_btn,
            text="抽選申し込み実行",
            command=self.start_apply_process,
            bg="#1e90ff",
            fg="white",
            font=("Arial", 12, "bold"),
            width=20,
        )
        self.submit_btn.pack()

        # 5. その他 枠
        frame_others = tk.LabelFrame(
            self.scrollable_frame, text="その他", font=("Arial", 10, "bold"), padx=15, pady=6
        )
        frame_others.pack(fill=tk.X, padx=15, pady=(3, 5))

        frame_others_btns = tk.Frame(frame_others)
        frame_others_btns.pack()

        self.result_btn = tk.Button(
            frame_others_btns,
            text="抽選結果確認実行",
            command=self.start_result_check_process,
            bg="#28a745",
            fg="white",
            font=("Arial", 12, "bold"),
            width=20,
        )
        self.result_btn.pack(side=tk.LEFT, padx=10)

        self.cancel_btn = tk.Button(
            frame_others_btns,
            text="抽選申込み取消実行",
            command=self.start_cancel_process,
            bg="#dc3545",
            fg="white",
            font=("Arial", 12, "bold"),
            width=20,
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=10)

        # 6. 利用者差し替え 枠
        frame_replace = tk.LabelFrame(
            self.scrollable_frame, text="利用者差し替え", font=("Arial", 10, "bold"), padx=15, pady=6
        )
        frame_replace.pack(fill=tk.X, padx=15, pady=(0, 10))

        frame_replace_ids = tk.Frame(frame_replace)
        frame_replace_ids.pack(fill=tk.X, pady=2)

        # 差し替え前
        tk.Label(frame_replace_ids, text="差し替え前 ID:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.old_id_entry = tk.Entry(frame_replace_ids, width=12, font=("Arial", 9))
        self.old_id_entry.pack(side=tk.LEFT, padx=2)
        tk.Label(frame_replace_ids, text="PW:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.old_pw_entry = tk.Entry(frame_replace_ids, width=8, font=("Arial", 9))
        self.old_pw_entry.insert(0, "000000")
        self.old_pw_entry.pack(side=tk.LEFT, padx=(2, 15))

        # 差し替え後
        tk.Label(frame_replace_ids, text="差し替え後 ID:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.new_id_entry = tk.Entry(frame_replace_ids, width=12, font=("Arial", 9))
        self.new_id_entry.pack(side=tk.LEFT, padx=2)
        tk.Label(frame_replace_ids, text="PW:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.new_pw_entry = tk.Entry(frame_replace_ids, width=8, font=("Arial", 9))
        self.new_pw_entry.insert(0, "000000")
        self.new_pw_entry.pack(side=tk.LEFT, padx=2)

        # 対象グラウンド・日時選択枠
        row_frame_rep = tk.Frame(frame_replace)
        row_frame_rep.pack(fill=tk.X, pady=4)
        tk.Label(row_frame_rep, text="対象:", font=("Arial", 9, "bold"), width=5, anchor="w").pack(side=tk.LEFT)

        self.rep_ground_combo = ttk.Combobox(
            row_frame_rep, values=ALL_GROUNDS, state="readonly", width=GROUND_COMBO_WIDTH
        )
        self.rep_ground_combo.set("行田運動広場")
        self.rep_ground_combo.pack(side=tk.LEFT, padx=2)

        tk.Label(row_frame_rep, text="日:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 1))

        self.rep_year_combo = ttk.Combobox(row_frame_rep, values=YEAR_OPTIONS, state="readonly", width=6)
        self.rep_year_combo.set(REPLACE_DEFAULT_YEAR_STR)
        self.rep_year_combo.pack(side=tk.LEFT, padx=1)
        tk.Label(row_frame_rep, text="年", font=("Arial", 9)).pack(side=tk.LEFT)

        self.rep_month_combo = ttk.Combobox(row_frame_rep, values=MONTH_OPTIONS, state="readonly", width=4)
        self.rep_month_combo.set(REPLACE_DEFAULT_MONTH_STR)
        self.rep_month_combo.pack(side=tk.LEFT, padx=1)
        tk.Label(row_frame_rep, text="月", font=("Arial", 9)).pack(side=tk.LEFT)

        self.rep_day_combo = ttk.Combobox(row_frame_rep, values=DAY_OPTIONS, state="readonly", width=4)
        self.rep_day_combo.set(REPLACE_DEFAULT_DAY_STR)
        self.rep_day_combo.pack(side=tk.LEFT, padx=1)
        tk.Label(row_frame_rep, text="日", font=("Arial", 9)).pack(side=tk.LEFT)

        frame_rep_btn = tk.Frame(frame_replace)
        frame_rep_btn.pack(pady=(6, 3))
        self.replace_btn = tk.Button(
            frame_rep_btn,
            text="利用者差し替え実行",
            command=self.start_replace_process,
            bg="#fd7e14",
            fg="white",
            font=("Arial", 12, "bold"),
            width=20,
        )
        self.replace_btn.pack()

    def _on_window_close(self):
        if self.is_running:
            if messagebox.askyesno(
                "確認",
                "処理が実行中です。中止してアプリを終了しますか？",
                parent=self.root,
            ):
                self.is_stopped = True
                if self.driver:
                    with contextlib.suppress(Exception):
                        self.driver.quit()
                self.root.destroy()
        else:
            self.root.destroy()

    def _toggle_ui_state(self, state: str):
        def change_state(widget):
            try:
                if not isinstance(widget, (tk.Text, tk.Canvas, ttk.Scrollbar, tk.Frame, tk.LabelFrame, tk.Label)):
                    widget.config(state=state)
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                change_state(child)
        change_state(self.scrollable_frame)

    def _on_mousewheel(self, event):
        if event.delta:
            step = -1 if event.delta > 0 else 1
            self.main_canvas.yview_scroll(step, "units")
        return "break"

    def _on_id_mousewheel(self, event):
        if event.delta:
            step = -1 if event.delta > 0 else 1
            self.id_canvas.yview_scroll(step, "units")
        return "break"

    def _on_global_mousewheel(self, event):
        widget = event.widget
        while widget is not None:
            if widget in (self.id_canvas, self.id_container_frame):
                return self._on_id_mousewheel(event)
            widget = widget.master
        return self._on_mousewheel(event)

    def append_log(self, text: str):
        self.log_queue.put(text)

    def _check_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n")

            num_lines = int(self.log_text.index("end-1c").split(".")[0])
            if num_lines > self.max_log_lines:
                self.log_text.delete("1.0", f"{num_lines - self.max_log_lines}.0")

            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(100, self._check_log_queue)

    def add_id_row(self, user_id: str = "", password: str = "000000"):
        row_idx = len(self.id_entries)
        row_frame = tk.Frame(self.id_container_frame)
        row_frame.pack(fill=tk.X, pady=2)

        row_label = tk.Label(row_frame, text=f"{row_idx+1}:", width=3, anchor="e", font=("Arial", 9))
        row_label.pack(side=tk.LEFT)

        id_entry = tk.Entry(row_frame, width=14, font=("Arial", 9))
        if user_id:
            id_entry.insert(0, user_id)
        id_entry.pack(side=tk.LEFT, padx=2)
        self.id_entries.append(id_entry)

        pw_entry = tk.Entry(row_frame, width=10, font=("Arial", 9))
        pw_entry.insert(0, password)
        pw_entry.pack(side=tk.LEFT, padx=2)
        self.pw_entries.append(pw_entry)

        for widget in (row_frame, row_label, id_entry, pw_entry):
            widget.bind("<MouseWheel>", self._on_id_mousewheel)
        self.root.after_idle(self._refresh_id_scrollregion)

    def _refresh_id_scrollregion(self):
        bbox = self.id_canvas.bbox("all")
        if bbox:
            self.id_canvas.configure(scrollregion=bbox)

    def clear_id_rows(self):
        for widget in self.id_container_frame.winfo_children():
            widget.destroy()
        self.id_entries.clear()
        self.pw_entries.clear()
        self.root.after_idle(self._refresh_id_scrollregion)

    def clear_paste_entry(self):
        self.paste_entry.delete(0, tk.END)
        self.paste_entry.focus_set()

    def show_paste_context_menu(self, event):
        self.paste_entry.focus_set()
        self.paste_entry.icursor(self.paste_entry.index(f"@{event.x}"))
        try:
            self.paste_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.paste_context_menu.grab_release()
        return "break"

    def paste_from_context_menu(self):
        self.paste_entry.event_generate("<<Paste>>")

    def clear_login_info(self):
        self.clear_id_rows()
        self.id_canvas.yview_moveto(0)
        self.append_log("【通知】ログイン情報をクリアしました。")

    def reflect_ids(self):
        paste_text = self.paste_entry.get().strip()
        if not paste_text:
            messagebox.showwarning("警告", "貼り付け欄が空です。")
            return

        zengaku = "０１２３４５６７８９"
        hangaku = "0123456789"
        converted_text = paste_text.translate(str.maketrans(zengaku, hangaku))
        digits_only = "".join([c for c in converted_text if c.isdigit()])

        if len(digits_only) < 10:
            messagebox.showwarning("警告", "有効なID（10桁の数字）が見つかりません。")
            return

        parsed_ids = [digits_only[i : i + 10] for i in range(0, len(digits_only), 10)]

        self.clear_id_rows()
        for u_id in parsed_ids:
            self.add_id_row(user_id=u_id, password="000000")

        self.id_canvas.yview_moveto(0)
        self.append_log(f"【通知】{len(parsed_ids)}件のIDを一括セットしました。")

    def _on_ground_combo_change(self, idx: int):
        chosen_ground = self.ground_combos[idx].get()

        sub_options = SUB_FACILITIES.get(chosen_ground, ["※詳細指定なし"])
        self.sub_combos[idx]["values"] = sub_options
        self.sub_combos[idx].current(0)

        if chosen_ground in SUB_FACILITIES:
            self.sub_combos[idx].config(state="readonly")
        else:
            self.sub_combos[idx].config(state="disabled")

        time_slots_dict = GROUND_TIME_SLOTS.get(chosen_ground, GROUND_TIME_SLOTS["行田運動広場"])
        self.time_combos[idx]["values"] = list(time_slots_dict.keys())
        self.time_combos[idx].current(0)

    def stop_process(self):
        self.is_stopped = True
        self.append_log("⏹ 中止ボタンが押されました。現在の処理完了後に安全停止します...")
        if self.stop_win and self.stop_win.winfo_exists():
            self.stop_win.destroy()

    def create_stop_floating_window(self):
        self.stop_win = tk.Toplevel(self.root)
        self.stop_win.title("操作")
        self.stop_win.geometry("180x60+50+50")
        self.stop_win.attributes("-topmost", True)
        self.stop_win.resizable(False, False)

        self.stop_win.protocol("WM_DELETE_WINDOW", self.stop_process)

        btn = tk.Button(
            self.stop_win,
            text="⏹ 中止する",
            command=self.stop_process,
            bg="#dc143c",
            fg="white",
            font=("Arial", 11, "bold"),
        )
        btn.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def open_help_window(self):
        help_win = tk.Toplevel(self.root)
        help_win.title("ヘルプ - 操作方法")
        help_win.geometry("580x320")
        help_win.resizable(False, False)

        help_text = (
            "【自動抽選申込ツールの使い方】\n\n"
            "・スプレッドシートの10桁IDを範囲選択してからコピーし、貼り付け欄にペーストしたら、「一括反映」を押してください。パスワードが違う場合は編集してください。\n\n"
            "・第1から第4まで、申込内容を入力して、「抽選申し込み実行」を押してください。\n\n"
            "・すべて終わったら、表示された画像を確認して、申込内容に間違いがないか確認し、終了です。\n\n"
            "※「動作設定」について\n"
            "・『画面を表示しない』：ブラウザを裏で動かすため処理が非常に速くなりますが、サイト仕様によりエラーが出る場合があります。\n"
            "・『ゆっくり動作させる』：PCや回線が重い時に、確実に画面表示を待ってから操作するための安全機能です。"
        )

        txt = tk.Text(help_win, font=("Arial", 10), padx=15, pady=15, wrap=tk.WORD)
        txt.insert(tk.END, help_text)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)

    def _get_credentials(self):
        credentials = []
        for i in range(len(self.id_entries)):
            user_id = self.id_entries[i].get().strip()
            password = self.pw_entries[i].get().strip()
            if user_id:
                credentials.append((user_id, password))
        return credentials

    def _execute_task(self, task_name: str, folder_prefix: str, run_single_func, extra_args=(), create_folder: bool = True):
        if self.is_running:
            messagebox.showwarning("警告", "現在処理が実行中です。")
            return

        credentials = self._get_credentials()
        if not credentials:
            messagebox.showwarning("警告", "有効なログインIDがセットされていません。")
            return

        self.is_stopped = False
        self.is_running = True
        
        self._toggle_ui_state("disabled")

        use_headless = self.headless_var.get()
        use_slow_mode = self.slow_mode_var.get()
        zoom_level = self.zoom_combo.get()

        thread = threading.Thread(
            target=self._worker_thread,
            args=(task_name, folder_prefix, run_single_func, credentials, use_headless, use_slow_mode, zoom_level, extra_args, create_folder),
            daemon=True,
        )
        thread.start()

    def _worker_thread(self, task_name, folder_prefix, run_single_func, credentials, use_headless, use_slow_mode, zoom_level, extra_args, create_folder):
        output_folder = ""
        if create_folder:
            now = datetime.datetime.now()
            folder_name = f"{folder_prefix}{now.year}年{now.month}月{now.day}日{now.hour}時{now.minute}分"
            desktop_path = get_real_desktop_path()
            output_folder = os.path.join(desktop_path, folder_name)
            os.makedirs(output_folder, exist_ok=True)
            self.append_log(f"📁 保存先: {output_folder}")

        options = webdriver.EdgeOptions()
        options.unhandled_prompt_behavior = "accept"
        options.add_experimental_option("detach", True)

        if use_headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1280,1024")
            options.add_argument("--disable-gpu")

        service = EdgeService()
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            service.creation_flags = subprocess.CREATE_NO_WINDOW

        mode_text = ""
        if use_headless: mode_text += "[画面非表示] "
        if use_slow_mode: mode_text += "[ゆっくり動作] "
        self.append_log(f"🚀 {task_name}処理を開始します {mode_text}")

        self.root.after(0, self.create_stop_floating_window)

        try:
            self.driver = webdriver.Edge(options=options, service=service)
            bot = FunabashiBot(
                self.driver, self.append_log, output_folder, stop_checker=lambda: self.is_stopped, slow_mode=use_slow_mode, zoom=zoom_level
            )

            success_count = 0
            for idx, (u_id, u_pw) in enumerate(credentials, start=1):
                if self.is_stopped:
                    self.append_log("⏹ ユーザーによって中止されました。")
                    break

                self.append_log(f"\n--- [{idx}/{len(credentials)} 件目] ID: {u_id} ---")

                try:
                    run_single_func(bot, u_id, u_pw, idx, *extra_args)
                    success_count += 1
                except InterruptedError:
                    self.append_log("⏹ ユーザーにより途中で停止されました。")
                    break
                except Exception as e_single:
                    clean_msg = clean_exception_msg(e_single)
                    self.append_log(f"⛔ エラー停止: {clean_msg}")
                    self.root.after(
                        0,
                        lambda u=u_id, msg=clean_msg: messagebox.showerror(
                            "エラー停止", f"ID: {u} の処理中に停止しました。\n\n原因: {msg}"
                        ),
                    )
                    return

            if not self.is_stopped:
                self.append_log(f"\n🎉 完了！ ({len(credentials)}件中 {success_count}件 完了)")

                if create_folder and output_folder:
                    with contextlib.suppress(Exception):
                        os.startfile(output_folder)

                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "確認", "画像ファイルを開き、確認してください。" if create_folder else "取消処理が完了しました。"
                    ),
                )

        except Exception as e:
            clean_msg = clean_exception_msg(e)
            self.append_log(f"⛔ システムエラー停止: {clean_msg}")
            self.root.after(
                0, lambda msg=clean_msg: messagebox.showerror("エラー停止", f"エラーが発生したため停止しました:\n{msg}")
            )
        finally:
            if self.driver:
                with contextlib.suppress(Exception):
                    self.driver.quit()
            self.driver = None

            self.is_running = False
            self.root.after(0, lambda: self._toggle_ui_state("normal"))
            self.root.after(0, self._restore_combobox_states)

            if self.stop_win and self.stop_win.winfo_exists():
                self.root.after(0, self.stop_win.destroy)

    def _restore_combobox_states(self):
        self.zoom_combo.config(state="readonly")
        self.people_combo.config(state="readonly")
        for i in range(4):
            self.ground_combos[i].config(state="readonly")
            self.year_combos[i].config(state="readonly")
            self.month_combos[i].config(state="readonly")
            self.day_combos[i].config(state="readonly")
            self.time_combos[i].config(state="readonly")
            self._on_ground_combo_change(i)
        
        self.rep_ground_combo.config(state="readonly")
        self.rep_year_combo.config(state="readonly")
        self.rep_month_combo.config(state="readonly")
        self.rep_day_combo.config(state="readonly")

    def start_apply_process(self):
        requests_list = []
        for i in range(4):
            y = self.year_combos[i].get()
            m = self.month_combos[i].get()
            d = self.day_combos[i].get()
            try:
                valid_date = datetime.date(int(y), int(m), int(d))
                t_date = valid_date.strftime("%Y%m%d")
            except ValueError:
                messagebox.showerror("エラー", f"第{i+1}希望の「{y}年{m}月{d}日」は存在しない日付です。")
                return

            chosen_ground = self.ground_combos[i].get()
            time_slots_dict = GROUND_TIME_SLOTS.get(chosen_ground, GROUND_TIME_SLOTS["行田運動広場"])
            t_label = self.time_combos[i].get()
            start_code, end_code = time_slots_dict[t_label]

            requests_list.append({
                "ground": chosen_ground,
                "sub": self.sub_combos[i].get(),
                "date": t_date,
                "start": start_code,
                "end": end_code,
            })

        chosen_people = self.people_combo.get()

        def _apply_task(bot, u_id, u_pw, idx, reqs, people):
            bot.run_single_id_apply(u_id, u_pw, reqs, people, id_index=idx)

        self._execute_task(
            task_name="抽選申し込み",
            folder_prefix="抽選申し込み内容",
            run_single_func=_apply_task,
            extra_args=(requests_list, chosen_people),
            create_folder=True,
        )

    def start_result_check_process(self):
        def _result_task(bot, u_id, u_pw, idx):
            bot.run_single_id_result(u_id, u_pw, id_index=idx)

        self._execute_task(
            task_name="抽選結果確認",
            folder_prefix="抽選結果確認",
            run_single_func=_result_task,
            create_folder=True,
        )

    def start_cancel_process(self):
        def _cancel_task(bot, u_id, u_pw, idx):
            bot.run_single_id_cancel(u_id, u_pw, id_index=idx)

        self._execute_task(
            task_name="抽選申込み取消",
            folder_prefix="抽選申込み取消",
            run_single_func=_cancel_task,
            create_folder=False,
        )

    # ==========================================
    # 利用者差し替え機能の処理
    # ==========================================
    def start_replace_process(self):
        old_id = self.old_id_entry.get().strip()
        old_pw = self.old_pw_entry.get().strip()
        new_id = self.new_id_entry.get().strip()
        new_pw = self.new_pw_entry.get().strip()

        if not old_id or not new_id:
            messagebox.showwarning("警告", "差し替え前・差し替え後のIDを両方入力してください。")
            return

        if self.is_running:
            messagebox.showwarning("警告", "現在処理が実行中です。")
            return

        # 画面のUIから対象グラウンドを取得
        rep_ground = self.rep_ground_combo.get()
        y = self.rep_year_combo.get()
        m = self.rep_month_combo.get()
        d = self.rep_day_combo.get()
        try:
            rep_date = datetime.date(int(y), int(m), int(d)).strftime("%Y%m%d")
        except ValueError:
            messagebox.showerror("エラー", f"利用者差し替えの「{y}年{m}月{d}日」は存在しない日付です。")
            return

        self.is_stopped = False
        self.is_running = True
        self._toggle_ui_state("disabled")

        thread = threading.Thread(
            target=self._worker_replace_thread,
            args=(old_id, old_pw, new_id, new_pw, rep_ground, rep_date),
            daemon=True,
        )
        thread.start()

    def _worker_replace_thread(self, old_id, old_pw, new_id, new_pw, rep_ground, rep_date):
        self.append_log("🚀 利用者差し替え処理を開始します")
        self.root.after(0, self.create_stop_floating_window)

        edge_driver = None
        chrome_driver = None

        try:
            # --- Edge (差し替え前) ---
            self.append_log("起動中: Edge (差し替え前アカウント)")
            edge_options = webdriver.EdgeOptions()
            edge_options.add_experimental_option("detach", True)
            edge_service = EdgeService()
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                edge_service.creation_flags = subprocess.CREATE_NO_WINDOW
            edge_driver = webdriver.Edge(options=edge_options, service=edge_service)

            bot_edge = FunabashiBot(
                edge_driver, self.append_log, stop_checker=lambda: self.is_stopped, slow_mode=False
            )
            bot_edge.login(old_id, old_pw)
            self.append_log(f"✅ Edgeログイン完了: {old_id}")
            self.append_log("    予約の取消画面へ移動中...")
            bot_edge.navigate_to_replace_old_cancel()
            self.append_log("    ✅ 予約の取消画面へ移動完了")
            time.sleep(1)

            # --- Chrome (差し替え後) ---
            self.append_log("起動中: Chrome (差し替え後アカウント)")
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_experimental_option("detach", True)
            chrome_service = ChromeService()
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                chrome_service.creation_flags = subprocess.CREATE_NO_WINDOW
            chrome_driver = webdriver.Chrome(options=chrome_options, service=chrome_service)

            bot_chrome = FunabashiBot(
                chrome_driver, self.append_log, stop_checker=lambda: self.is_stopped, slow_mode=False
            )
            bot_chrome.login(new_id, new_pw)
            self.append_log(f"✅ Chromeログイン完了: {new_id}")
            
            # --- 画面遷移の実行 ---
            self.append_log(f"    画面遷移中（予約の申込み → 複合検索 → 利用目的 → 軟式野球 → 館の選択 → {rep_ground} → 検索開始）...")
            bot_chrome.navigate_to_replace_new_search(rep_ground, rep_date)
            self.append_log(f"    ✅ 検索開始まで完了（{rep_date[:4]}年{rep_date[4:6]}月{rep_date[6:]}日）")
            # ----------------------------------------

            self.append_log("\n🎉 ブラウザの起動とログインが完了しました")
            self.root.after(0, lambda: messagebox.showinfo("確認", "各ブラウザで必要な画面まで移動しました。\n手動で操作を続けてください。"))

        except Exception as e:
            clean_msg = clean_exception_msg(e)
            self.append_log(f"⛔ エラー停止: {clean_msg}")
            self.root.after(0, lambda msg=clean_msg: messagebox.showerror("エラー停止", f"エラーが発生しました:\n{msg}"))
            
            if edge_driver:
                with contextlib.suppress(Exception): edge_driver.quit()
            if chrome_driver:
                with contextlib.suppress(Exception): chrome_driver.quit()
        finally:
            self.is_running = False
            self.root.after(0, lambda: self._toggle_ui_state("normal"))
            self.root.after(0, self._restore_combobox_states)
            if self.stop_win and self.stop_win.winfo_exists():
                self.root.after(0, self.stop_win.destroy)

# ==========================================
# エントリポイント
# ==========================================
if __name__ == "__main__":
    root = tk.Tk()
    
    root.withdraw() 
    check_and_install_libraries(root)
    root.deiconify() 

    app = FunabashiApp(root)
    root.mainloop()
