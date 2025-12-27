"""
네이버 쇼핑 순위 확인 프로그램
"""
 
import sys
import os
import json
import urllib.request
import urllib.parse
import urllib.error
import re
from datetime import datetime
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextBrowser, QTextEdit,
    QMessageBox, QSpacerItem, QSizePolicy, QProgressBar,
    QTabWidget, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QComboBox, QCheckBox, QSpinBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'  # Windows 기본 한글 폰트
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QKeyEvent, QIcon, QColor

# API 키 설정 (기본값 - 사용자가 직접 입력)
client_id = ""
client_secret = ""
CUSTOMER_ID = ""
ACCESS_LICENSE = ""
SECRET_KEY = ""

# API 키 저장 파일
API_CONFIG_FILE = "api_config.json"
RANK_TRACKING_FILE = "rank_tracking.json"

def load_api_config():
    """저장된 API 설정 불러오기"""
    global client_id, client_secret, CUSTOMER_ID, ACCESS_LICENSE, SECRET_KEY
    if os.path.exists(API_CONFIG_FILE):
        try:
            with open(API_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                client_id = config.get("client_id", client_id)
                client_secret = config.get("client_secret", client_secret)
                CUSTOMER_ID = config.get("customer_id", "")
                ACCESS_LICENSE = config.get("access_license", "")
                SECRET_KEY = config.get("secret_key", "")
        except Exception as e:
            print(f"⚠️ API 설정 로드 실패: {e}")

def save_api_config():
    """API 설정 저장"""
    config = {
        "client_id": client_id,
        "client_secret": client_secret,
        "customer_id": CUSTOMER_ID,
        "access_license": ACCESS_LICENSE,
        "secret_key": SECRET_KEY
    }
    try:
        with open(API_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ API 설정 저장 실패: {e}")
        return False

def verify_naver_api(client_id_val, client_secret_val):
    """네이버 API 인증 확인"""
    try:
        # 간단한 검색 요청으로 인증 확인 (한글 쿼리는 URL 인코딩 필요)
        test_query = urllib.parse.quote("테스트")
        test_url = f"https://openapi.naver.com/v1/search/shop.json?query={test_query}&display=1&start=1"
        request = urllib.request.Request(test_url)
        request.add_header("X-Naver-Client-Id", client_id_val)
        request.add_header("X-Naver-Client-Secret", client_secret_val)
        response = urllib.request.urlopen(request, timeout=5)
        result = json.loads(response.read())
        # 응답에 items가 있으면 인증 성공
        return "items" in result and len(result.get("items", [])) > 0
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False  # 인증 실패
        print(f"⚠️ HTTP 오류: {e.code} - {e.reason}")
        return False
    except Exception as e:
        print(f"⚠️ API 인증 확인 중 오류: {e}")
        return False

# 프로그램 시작 시 저장된 설정 불러오기
load_api_config()

class CustomTextEdit(QTextEdit):
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Tab and not event.modifiers():
            self.parent().focusNextChild()
        else:
            super().keyPressEvent(event)

class Worker(QThread):
    result_ready = Signal(str)
    progress_update = Signal(int, str)
    finished_all = Signal(dict)

    def __init__(self, keywords, mall_name):
        super().__init__()
        self.keywords = keywords
        self.mall_name = mall_name
        self.all_results = {}

    def get_top_ranked_product_by_mall(self, keyword, mall_name):
        encText = urllib.parse.quote(keyword)
        seen_titles = set()
        best_product = None
        try:
            for start in range(1, 1001, 100):
                url = f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=100&start={start}"
                request = urllib.request.Request(url)
                request.add_header("X-Naver-Client-Id", client_id)
                request.add_header("X-Naver-Client-Secret", client_secret)
                try:
                    response = urllib.request.urlopen(request, timeout=10)
                    result = json.loads(response.read())
                    items = result.get("items", [])
                    if not items:
                        break  # 더 이상 결과가 없으면 중단
                    for idx, item in enumerate(items, start=1):
                        if item.get("mallName") and mall_name in item["mallName"]:
                            title_clean = re.sub(r"<.*?>", "", item.get("title", ""))
                            if title_clean in seen_titles:
                                continue
                            seen_titles.add(title_clean)
                            rank = start + idx - 1
                            # 카테고리 정보 수집
                            cat1 = item.get("category1", "")
                            cat2 = item.get("category2", "")
                            cat3 = item.get("category3", "")
                            category = " > ".join(filter(None, [cat1, cat2, cat3]))
                            
                            product = {
                                "rank": rank,
                                "title": title_clean,
                                "price": item.get("lprice", "0"),
                                "link": item.get("link", ""),
                                "mallName": item.get("mallName", ""),
                                "brand": item.get("brand", ""),
                                "category": category
                            }
                            if not best_product or rank < best_product["rank"]:
                                best_product = product
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                    print(f"⚠️ 네이버 API 호출 실패 (start={start}): {e}")
                    break
        except Exception as e:
            print(f"⚠️ 검색 중 오류 발생: {e}")
        return best_product

    def run(self):
        total = len(self.keywords)
        for i, keyword in enumerate(self.keywords):
            result = self.get_top_ranked_product_by_mall(keyword, self.mall_name)
            if result:
                link_html = f'<a href="{result["link"]}" style="color:blue;">{result["link"]}</a>'
                brand_text = result.get("brand", "") if result.get("brand") else "-"
                category_text = result.get("category", "") if result.get("category") else "-"
                html = (
                    f"<b>✅ {keyword}</b><br>"
                    f" - 순위: {result['rank']}위<br>"
                    f" - 상품명: {result['title']}<br>"
                    f" - 판매처: {result.get('mallName', '-')}<br>"
                    f" - 브랜드: {brand_text}<br>"
                    f" - 상품타입: {category_text}<br>"
                    f" - 가격: {int(result['price']):,}원<br>"
                    f" - 링크: {link_html}<br><br>"
                )
                self.all_results[keyword] = result
            else:
                html = f"<b style='color:red;'>❌ {keyword} → 검색 결과 없음</b><br><br>"
                self.all_results[keyword] = "검색 결과 없음"
            percent = int(((i+1)/total)*100)
            self.result_ready.emit(html)
            self.progress_update.emit(percent, keyword)
        self.finished_all.emit(self.all_results)

class ProductListWorker(QThread):
    """1~100위 상품 리스트 수집 Worker"""
    progress_update = Signal(int, str)
    finished = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, keyword):
        super().__init__()
        self.keyword = keyword
        self.products = []

    def run(self):
        try:
            encText = urllib.parse.quote(self.keyword)
            seen_titles = set()
            
            # 1~100위까지 수집 (display=100, start=1)
            url = f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=100&start=1"
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            response = urllib.request.urlopen(request, timeout=10)
            result = json.loads(response.read())
            items = result.get("items", [])
            
            for idx, item in enumerate(items, start=1):
                if idx > 100:
                    break
                
                title_clean = re.sub(r"<.*?>", "", item.get("title", ""))
                if title_clean in seen_titles:
                    continue
                seen_titles.add(title_clean)
                
                # 카테고리 정리
                cat1 = item.get("category1", "")
                cat2 = item.get("category2", "")
                cat3 = item.get("category3", "")
                category = " > ".join(filter(None, [cat1, cat2, cat3]))
                
                product = {
                    "순위": idx,
                    "상품명": title_clean,
                    "가격": int(item.get("lprice", 0)),
                    "카테고리": category,
                    "판매처": item.get("mallName", ""),
                    "브랜드": item.get("brand", ""),
                    "제조사": item.get("maker", ""),
                    "상품링크": item.get("link", ""),
                    "이미지": item.get("image", "")
                }
                self.products.append(product)
                
                # 진행률 업데이트
                percent = int((idx / 100) * 100)
                self.progress_update.emit(percent, f"{idx}위 수집 중...")
            
            self.finished.emit(self.products)
            
        except urllib.error.HTTPError as e:
            self.error_occurred.emit(f"HTTP 오류: {e.code} - {e.reason}")
        except Exception as e:
            self.error_occurred.emit(f"오류 발생: {str(e)}")

def save_to_excel(products, keyword, save_path=None):
    """상품 리스트를 엑셀 파일로 저장 (순위, 상품명, 판매처, 브랜드, 상품타입, 가격, 카테고리, 링크 순서)"""
    try:
        if not products:
            return False, "저장할 상품이 없습니다."
        
        # 순위, 상품명, 판매처, 브랜드, 상품타입, 가격, 링크 순서로 데이터 정리
        excel_data = []
        for product in products:
            excel_data.append({
                "순위": product.get("순위", ""),
                "상품명": product.get("상품명", ""),
                "판매처": product.get("판매처", ""),
                "브랜드": product.get("브랜드", "") if product.get("브랜드") else "",
                "상품타입": product.get("카테고리", ""),
                "가격": product.get("가격", 0),
                "링크": product.get("상품링크", "")
            })
        
        # DataFrame 생성
        df = pd.DataFrame(excel_data)
        
        if save_path:
            filename = save_path
        else:
            # 파일명 생성 (검색어_날짜시간.xlsx)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_keyword = re.sub(r'[<>:"/\\|?*]', '_', keyword)  # 파일명에 사용할 수 없는 문자 제거
            filename = f"상품리스트_{safe_keyword}_{timestamp}.xlsx"
        
        # 엑셀 파일로 저장
        df.to_excel(filename, index=False, engine='openpyxl')
        
        return True, filename
    except Exception as e:
        return False, f"엑셀 저장 실패: {str(e)}"

def load_tracking_data():
    """순위 추적 데이터 불러오기"""
    if os.path.exists(RANK_TRACKING_FILE):
        try:
            with open(RANK_TRACKING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 추적 데이터 로드 실패: {e}")
    return {}

def save_tracking_data(data):
    """순위 추적 데이터 저장"""
    try:
        with open(RANK_TRACKING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ 추적 데이터 저장 실패: {e}")
        return False

def get_product_rank(keyword, mall_name, product_name=None):
    """특정 상품의 순위 조회"""
    encText = urllib.parse.quote(keyword)
    seen_titles = set()
    best_product = None
    
    try:
        for start in range(1, 1001, 100):
            url = f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=100&start={start}"
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            response = urllib.request.urlopen(request, timeout=10)
            result = json.loads(response.read())
            items = result.get("items", [])
            
            if not items:
                break
                
            for idx, item in enumerate(items, start=1):
                if item.get("mallName") and mall_name in item["mallName"]:
                    title_clean = re.sub(r"<.*?>", "", item.get("title", ""))
                    
                    # 상품명이 지정된 경우 정확히 일치하는지 확인
                    if product_name and product_name.strip():
                        if product_name.strip() not in title_clean:
                            continue
                    
                    if title_clean in seen_titles:
                        continue
                    seen_titles.add(title_clean)
                    
                    rank = start + idx - 1
                    product = {
                        "rank": rank,
                        "title": title_clean,
                        "price": int(item.get("lprice", 0)),
                        "link": item.get("link", ""),
                        "mallName": item.get("mallName", "")
                    }
                    
                    if not best_product or rank < best_product["rank"]:
                        best_product = product
                        
        return best_product
    except Exception as e:
        print(f"⚠️ 순위 조회 중 오류: {e}")
        return None

def get_competitor_products(keyword, target_mall_name, competitor_count=10):
    """입력한 판매처 상품 주변의 경쟁사 상품들 조회"""
    encText = urllib.parse.quote(keyword)
    target_product = None
    all_products = []
    
    try:
        # 먼저 입력한 판매처의 상품 찾기
        for start in range(1, 1001, 100):
            url = f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=100&start={start}"
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            response = urllib.request.urlopen(request, timeout=10)
            result = json.loads(response.read())
            items = result.get("items", [])
            
            if not items:
                break
            
            for idx, item in enumerate(items, start=1):
                rank = start + idx - 1
                title_clean = re.sub(r"<.*?>", "", item.get("title", ""))
                mall_name = item.get("mallName", "")
                
                product = {
                    "rank": rank,
                    "title": title_clean,
                    "price": int(item.get("lprice", 0)),
                    "link": item.get("link", ""),
                    "mallName": mall_name
                }
                
                # 입력한 판매처의 상품 찾기
                if not target_product and mall_name and target_mall_name in mall_name:
                    target_product = product
                
                all_products.append(product)
        
        if not target_product:
            return None, []
        
        target_rank = target_product["rank"]
        
        # 타겟 상품 주변의 다른 판매처 상품들 찾기
        competitors = []
        seen_malls = set()
        
        # 타겟 상품 위아래로 경쟁사 찾기
        for product in all_products:
            # 같은 판매처는 제외
            if product["mallName"] and target_mall_name in product["mallName"]:
                continue
            
            # 타겟 순위 주변 ±5개 범위
            rank_diff = abs(product["rank"] - target_rank)
            if rank_diff <= 5 and product["rank"] != target_rank:
                # 중복 판매처 제거 (같은 판매처는 하나만)
                if product["mallName"] not in seen_malls:
                    competitors.append(product)
                    seen_malls.add(product["mallName"])
        
        # 경쟁사가 부족하면 범위 확대
        if len(competitors) < competitor_count:
            for product in all_products:
                if product["mallName"] and target_mall_name in product["mallName"]:
                    continue
                
                rank_diff = abs(product["rank"] - target_rank)
                if 5 < rank_diff <= 10 and product["mallName"] not in seen_malls:
                    competitors.append(product)
                    seen_malls.add(product["mallName"])
                    if len(competitors) >= competitor_count:
                        break
        
        # 순위 순으로 정렬
        competitors.sort(key=lambda x: x["rank"])
        
        return target_product, competitors[:competitor_count]
        
    except Exception as e:
        print(f"⚠️ 경쟁사 조회 중 오류: {e}")
        return None, []

def resource_path(relative_path):
    """PyInstaller 환경에서도 리소스 파일 경로를 올바르게 반환"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class RankCheckerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 순위 확인기")
        self.setWindowIcon(QIcon(resource_path("logo_inner.ico")))
        self.resize(1000, 900)  # 창 크기 확대
        self.api_verified = False  # API 인증 상태
        self.setup_ui()
        # GUI가 표시된 후에 체크 실행
        QTimer.singleShot(100, self.check_status_after_init)

    def setup_ui(self):
        # 친환경적인 전체 스타일 적용
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f9f6;
                font-family: 'Malgun Gothic', '맑은 고딕', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #c8e6c9;
                background-color: #ffffff;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #e8f5e9;
                color: #2e7d32;
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
            }
            QTabBar::tab:selected {
                background-color: #4caf50;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #81c784;
                color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                color: #2e7d32;
                border: 2px solid #a5d6a7;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #f1f8f4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }
            QLineEdit, QTextEdit {
                border: 2px solid #a5d6a7;
                border-radius: 6px;
                padding: 8px;
                background-color: #ffffff;
                font-size: 10pt;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 2px solid #4caf50;
                background-color: #f9fff9;
            }
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #4caf50);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 10pt;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #81c784, stop:1 #66bb6a);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4caf50, stop:1 #388e3c);
            }
            QPushButton:disabled {
                background-color: #c8e6c9;
                color: #9e9e9e;
            }
            QProgressBar {
                border: 2px solid #a5d6a7;
                border-radius: 8px;
                text-align: center;
                background-color: #e8f5e9;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #66bb6a, stop:1 #4caf50);
                border-radius: 6px;
            }
            QTableWidget {
                border: 2px solid #a5d6a7;
                border-radius: 8px;
                background-color: #ffffff;
                gridline-color: #c8e6c9;
                selection-background-color: #c8e6c9;
                selection-color: #1b5e20;
            }
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            QTableWidget::item:alternate {
                background-color: #f1f8f4;
            }
            QTableWidget::item:selected {
                background-color: #a5d6a7;
                color: #1b5e20;
            }
            QHeaderView::section {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #4caf50);
                color: #ffffff;
                padding: 10px;
                border: none;
                font-weight: bold;
                font-size: 10pt;
            }
            QTextBrowser {
                border: 2px solid #a5d6a7;
                border-radius: 8px;
                background-color: #ffffff;
                padding: 10px;
            }
            QLabel {
                color: #2e7d32;
            }
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 탭 위젯 생성
        self.tabs = QTabWidget()
        
        # 메인 탭
        main_tab = QWidget()
        main_tab_layout = QVBoxLayout()
        bold_font = QFont()
        bold_font.setBold(True)

        self.label_keywords = QLabel("검색어(최대 10개, 쉼표로 구분)")
        self.label_keywords.setFont(bold_font)
        self.input_keywords = CustomTextEdit(main_tab)
        self.input_keywords.setFixedHeight(70)
        self.input_keywords.setPlaceholderText("예: 키보드, 마우스, 충전기")

        main_tab_layout.addWidget(self.label_keywords)
        main_tab_layout.addWidget(self.input_keywords)
        main_tab_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.label_mall = QLabel("판매처명 (예: OO스토어)")
        self.label_mall.setFont(bold_font)
        self.input_mall = QLineEdit()

        main_tab_layout.addWidget(self.label_mall)
        main_tab_layout.addWidget(self.input_mall)
        main_tab_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.button_check = QPushButton("🌿 순위 확인")
        self.button_check.setFont(bold_font)
        self.button_check.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #4caf50);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 15px 30px;
                font-weight: bold;
                font-size: 12pt;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #81c784, stop:1 #66bb6a);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4caf50, stop:1 #388e3c);
            }
        """)
        self.button_check.clicked.connect(self.start_check)

        main_tab_layout.addWidget(self.button_check)
        main_tab_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
        
        # 엑셀 다운로드 버튼
        self.button_excel = QPushButton("📊 엑셀 다운로드")
        self.button_excel.setFont(bold_font)
        self.button_excel.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #81c784, stop:1 #66bb6a);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 11pt;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #a5d6a7, stop:1 #81c784);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #4caf50);
            }
            QPushButton:disabled {
                background-color: #c8e6c9;
                color: #9e9e9e;
            }
        """)
        self.button_excel.clicked.connect(self.download_main_excel)
        self.button_excel.setEnabled(False)  # 초기에는 비활성화
        main_tab_layout.addWidget(self.button_excel)
        main_tab_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.label_status = QLabel("")
        self.result_display = QTextBrowser()
        self.result_display.setOpenExternalLinks(True)

        self.progress_bar = QProgressBar()
        main_tab_layout.addWidget(self.label_status)
        main_tab_layout.addWidget(self.progress_bar)
        main_tab_layout.addWidget(self.result_display)

        main_tab.setLayout(main_tab_layout)
        self.tabs.addTab(main_tab, "메인")
        
        # 상품 리스트 추출 탭
        product_list_tab = QWidget()
        product_list_layout = QVBoxLayout()
        self.setup_product_list_tab(product_list_tab, product_list_layout)
        product_list_tab.setLayout(product_list_layout)
        self.tabs.addTab(product_list_tab, "상품 리스트")
        
        # 순위 추적/모니터링 탭
        tracking_tab = QWidget()
        tracking_layout = QVBoxLayout()
        self.setup_rank_tracking_tab(tracking_tab, tracking_layout)
        tracking_tab.setLayout(tracking_layout)
        self.tabs.addTab(tracking_tab, "📈 순위 추적")
        
        # 경쟁사 분석 탭
        competitor_tab = QWidget()
        competitor_layout = QVBoxLayout()
        self.setup_competitor_analysis_tab(competitor_tab, competitor_layout)
        competitor_tab.setLayout(competitor_layout)
        self.tabs.addTab(competitor_tab, "⚔️ 경쟁사 분석")
        
        # 설정 탭
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        self.setup_settings_tab(settings_tab, settings_layout)
        settings_tab.setLayout(settings_layout)
        self.tabs.addTab(settings_tab, "설정")
        
        # 메인 레이아웃에 탭 추가
        main_layout.addWidget(self.tabs)
        
        # Footer
        footer = QLabel("네이버 순위 확인기")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("""
            QLabel {
                color: #66bb6a;
                font-size: 9pt;
                padding: 10px;
                background-color: #e8f5e9;
                border-radius: 6px;
            }
        """)
        main_layout.addWidget(footer)
        
        self.setLayout(main_layout)

        self.dots = ['.', '..', '...']
        self.dot_index = 0
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.animate_status)
    
    def setup_settings_tab(self, parent, layout):
        """설정 탭 UI 구성"""
        bold_font = QFont()
        bold_font.setBold(True)
        
        # API 키 설정 그룹
        api_group = QGroupBox("🔑 네이버 API 키 설정")
        api_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                color: #2e7d32;
                border: 2px solid #a5d6a7;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: #f1f8f4;
            }
        """)
        api_layout = QVBoxLayout()
        api_layout.setSpacing(12)
        
        # Client ID
        client_id_label = QLabel("Client ID:")
        client_id_label.setFont(bold_font)
        self.settings_client_id = QLineEdit()
        self.settings_client_id.setText(client_id)
        self.settings_client_id.setPlaceholderText("네이버 Client ID 입력")
        api_layout.addWidget(client_id_label)
        api_layout.addWidget(self.settings_client_id)
        
        # Client Secret
        client_secret_label = QLabel("Client Secret:")
        client_secret_label.setFont(bold_font)
        self.settings_client_secret = QLineEdit()
        self.settings_client_secret.setText(client_secret)
        self.settings_client_secret.setPlaceholderText("네이버 Client Secret 입력")
        self.settings_client_secret.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(client_secret_label)
        api_layout.addWidget(self.settings_client_secret)
        
        # Customer ID
        customer_id_label = QLabel("Customer ID:")
        customer_id_label.setFont(bold_font)
        self.settings_customer_id = QLineEdit()
        self.settings_customer_id.setText(CUSTOMER_ID)
        self.settings_customer_id.setPlaceholderText("Customer ID 입력")
        api_layout.addWidget(customer_id_label)
        api_layout.addWidget(self.settings_customer_id)
        
        # Access License
        access_license_label = QLabel("Access License:")
        access_license_label.setFont(bold_font)
        self.settings_access_license = QLineEdit()
        self.settings_access_license.setText(ACCESS_LICENSE)
        self.settings_access_license.setPlaceholderText("Access License 입력")
        api_layout.addWidget(access_license_label)
        api_layout.addWidget(self.settings_access_license)
        
        # Secret Key
        secret_key_label = QLabel("Secret Key:")
        secret_key_label.setFont(bold_font)
        self.settings_secret_key = QLineEdit()
        self.settings_secret_key.setText(SECRET_KEY)
        self.settings_secret_key.setPlaceholderText("Secret Key 입력")
        self.settings_secret_key.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(secret_key_label)
        api_layout.addWidget(self.settings_secret_key)
        
        # 인증 확인 버튼
        self.verify_button = QPushButton("✅ API 인증 확인")
        self.verify_button.setFont(bold_font)
        self.verify_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #4caf50);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 15px 30px;
                font-weight: bold;
                font-size: 11pt;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #81c784, stop:1 #66bb6a);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4caf50, stop:1 #388e3c);
            }
        """)
        self.verify_button.clicked.connect(self.verify_api_keys)
        api_layout.addWidget(self.verify_button)
        
        # 인증 상태 표시
        self.auth_status_label = QLabel("인증 상태: 미인증")
        self.auth_status_label.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-weight: bold;
                padding: 10px;
                background-color: #ffebee;
                border-radius: 6px;
                font-size: 10pt;
            }
        """)
        api_layout.addWidget(self.auth_status_label)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # 저장된 설정이 있고 인증이 되어 있으면 필드 비활성화
        if os.path.exists(API_CONFIG_FILE) and client_id and client_secret:
            # 저장된 설정으로 인증 확인
            QTimer.singleShot(500, self.check_saved_api_config)
    
    def setup_product_list_tab(self, parent, layout):
        """상품 리스트 추출 탭 UI 구성"""
        bold_font = QFont()
        bold_font.setBold(True)
        
        # 설명 라벨
        info_label = QLabel("🌱 검색어를 입력하면 1위~100위까지의 상품 리스트를 추출하여 표시합니다.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                color: #2e7d32;
                padding: 15px;
                background-color: #e8f5e9;
                border-radius: 8px;
                font-size: 10pt;
            }
        """)
        layout.addWidget(info_label)
        
        # 검색어 입력 그룹
        search_group = QGroupBox("🔍 검색 설정")
        search_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                color: #2e7d32;
                border: 2px solid #a5d6a7;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 15px;
                background-color: #f1f8f4;
            }
        """)
        search_layout = QVBoxLayout()
        search_layout.setSpacing(10)
        
        keyword_label = QLabel("검색어:")
        keyword_label.setFont(bold_font)
        self.product_list_keyword = QLineEdit()
        self.product_list_keyword.setPlaceholderText("예: 키보드, 마우스, 노트북")
        search_layout.addWidget(keyword_label)
        search_layout.addWidget(self.product_list_keyword)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # 버튼
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        self.extract_button = QPushButton("🌿 상품 리스트 추출")
        self.extract_button.setFont(bold_font)
        self.extract_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #4caf50);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 15px 30px;
                font-weight: bold;
                font-size: 11pt;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #81c784, stop:1 #66bb6a);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4caf50, stop:1 #388e3c);
            }
        """)
        self.extract_button.clicked.connect(self.start_product_extraction)
        button_layout.addWidget(self.extract_button)
        
        self.excel_download_button = QPushButton("📊 엑셀 다운로드")
        self.excel_download_button.setFont(bold_font)
        self.excel_download_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #42a5f5, stop:1 #1e88e5);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 15px 30px;
                font-weight: bold;
                font-size: 11pt;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #64b5f6, stop:1 #42a5f5);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e88e5, stop:1 #1565c0);
            }
            QPushButton:disabled {
                background-color: #b0bec5;
                color: #9e9e9e;
            }
        """)
        self.excel_download_button.clicked.connect(self.download_to_excel)
        self.excel_download_button.setEnabled(False)  # 초기에는 비활성화
        button_layout.addWidget(self.excel_download_button)
        
        layout.addLayout(button_layout)
        
        # 진행률 표시
        self.product_list_progress = QProgressBar()
        self.product_list_progress.setVisible(False)
        layout.addWidget(self.product_list_progress)
        
        self.product_list_status = QLabel("")
        self.product_list_status.setStyleSheet("""
            QLabel {
                font-weight: bold;
                padding: 10px;
                background-color: #e8f5e9;
                border-radius: 6px;
                color: #2e7d32;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.product_list_status)
        
        # 결과 표시 영역 - 테이블
        result_label = QLabel("📋 추출된 상품 정보:")
        result_label.setFont(bold_font)
        result_label.setStyleSheet("""
            QLabel {
                color: #2e7d32;
                font-size: 12pt;
                padding: 5px;
            }
        """)
        layout.addWidget(result_label)
        
        # 테이블 위젯 생성
        self.product_list_table = QTableWidget()
        self.product_list_table.setColumnCount(7)
        self.product_list_table.setHorizontalHeaderLabels(["순위", "상품명", "판매처", "브랜드", "상품타입", "가격", "링크"])
        
        # 좌측 행 번호 숨기기
        self.product_list_table.verticalHeader().setVisible(False)
        
        # 테이블 설정
        header = self.product_list_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # 순위
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # 상품명
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 판매처
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 브랜드
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # 상품타입
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # 가격
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # 링크
        
        self.product_list_table.setAlternatingRowColors(True)
        self.product_list_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.product_list_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # 테이블이 더 많은 공간을 차지하도록 설정
        self.product_list_table.setMinimumHeight(500)  # 최소 높이 설정
        self.product_list_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout.addWidget(self.product_list_table, stretch=1)  # stretch를 1로 설정하여 더 많은 공간 할당
        
        # 저장된 상품 데이터 (엑셀 다운로드용)
        self.current_products = []
    
    def start_product_extraction(self):
        """상품 리스트 추출 시작"""
        keyword = self.product_list_keyword.text().strip()
        
        if not keyword:
            QMessageBox.warning(self, "입력 오류", "검색어를 입력하세요.")
            return
        
        if not client_id or not client_secret:
            QMessageBox.warning(self, "API 설정 오류", "먼저 설정 탭에서 API 키를 인증하세요.")
            return
        
        # 기존 Worker가 실행 중이면 중지
        if hasattr(self, 'product_list_worker') and self.product_list_worker.isRunning():
            self.product_list_worker.terminate()
            self.product_list_worker.wait()
        
        # UI 초기화
        self.product_list_table.setRowCount(0)  # 테이블 초기화
        self.product_list_progress.setValue(0)
        self.product_list_progress.setVisible(True)
        self.product_list_status.setText("🔄 상품 리스트 수집 중...")
        self.extract_button.setEnabled(False)
        self.excel_download_button.setEnabled(False)  # 엑셀 다운로드 버튼도 비활성화
        
        # Worker 시작
        self.product_list_worker = ProductListWorker(keyword)
        self.product_list_worker.progress_update.connect(self.update_product_list_progress)
        self.product_list_worker.finished.connect(self.on_product_extraction_finished)
        self.product_list_worker.error_occurred.connect(self.on_product_extraction_error)
        self.product_list_worker.start()
    
    def update_product_list_progress(self, percent, message):
        """상품 리스트 추출 진행률 업데이트"""
        self.product_list_progress.setValue(percent)
        self.product_list_status.setText(f"🔄 {message}")
    
    def on_product_extraction_finished(self, products):
        """상품 리스트 추출 완료"""
        self.product_list_progress.setValue(100)
        self.extract_button.setEnabled(True)
        
        if not products:
            self.product_list_status.setText("❌ 추출된 상품이 없습니다.")
            self.excel_download_button.setEnabled(False)
            QMessageBox.warning(self, "결과 없음", "검색 결과가 없습니다.")
            return
        
        # 상품 데이터 저장 (엑셀 다운로드용)
        self.current_products = products
        
        # 테이블에 데이터 표시
        self.product_list_table.setRowCount(len(products))
        
        for row, product in enumerate(products):
            # 순위
            rank_item = QTableWidgetItem(str(product.get("순위", "")))
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.product_list_table.setItem(row, 0, rank_item)
            
            # 상품명
            name_item = QTableWidgetItem(product.get("상품명", ""))
            self.product_list_table.setItem(row, 1, name_item)
            
            # 판매처
            mall_item = QTableWidgetItem(product.get("판매처", ""))
            self.product_list_table.setItem(row, 2, mall_item)
            
            # 브랜드
            brand_item = QTableWidgetItem(product.get("브랜드", "") if product.get("브랜드") else "")
            self.product_list_table.setItem(row, 3, brand_item)
            
            # 상품타입 (카테고리)
            category_item = QTableWidgetItem(product.get("카테고리", ""))
            self.product_list_table.setItem(row, 4, category_item)
            
            # 가격
            price = product.get("가격", 0)
            price_item = QTableWidgetItem(f"{price:,}원")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.product_list_table.setItem(row, 5, price_item)
            
            # 링크
            link_item = QTableWidgetItem(product.get("상품링크", ""))
            self.product_list_table.setItem(row, 6, link_item)
        
        # 테이블 스크롤을 맨 위로
        self.product_list_table.scrollToTop()
        
        # 상태 업데이트
        self.product_list_status.setText(f"✅ 추출 완료! {len(products)}개 상품 수집")
        
        # 엑셀 다운로드 버튼 활성화
        self.excel_download_button.setEnabled(True)
        
        QMessageBox.information(
            self, 
            "추출 완료", 
            f"총 {len(products)}개 상품이 추출되었습니다.\n\n엑셀 다운로드 버튼을 클릭하여 파일로 저장하세요."
        )
    
    def download_to_excel(self):
        """엑셀 파일로 다운로드"""
        if not self.current_products:
            QMessageBox.warning(self, "데이터 없음", "저장할 상품 데이터가 없습니다.")
            return
        
        # 파일 저장 대화상자
        keyword = self.product_list_keyword.text().strip() or "상품리스트"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_keyword = re.sub(r'[<>:"/\\|?*]', '_', keyword)
        default_filename = f"상품리스트_{safe_keyword}_{timestamp}.xlsx"
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "엑셀 파일 저장",
            default_filename,
            "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if filename:
            success, message = save_to_excel(self.current_products, keyword, filename)
            
            if success:
                QMessageBox.information(
                    self,
                    "저장 완료",
                    f"엑셀 파일이 저장되었습니다.\n\n파일명: {message}"
                )
            else:
                QMessageBox.critical(self, "저장 실패", message)
    
    def on_product_extraction_error(self, error_message):
        """상품 리스트 추출 오류"""
        self.product_list_progress.setValue(0)
        self.extract_button.setEnabled(True)
        self.product_list_status.setText(f"❌ 오류: {error_message}")
        QMessageBox.critical(self, "오류 발생", error_message)
    
    def verify_api_keys(self):
        """API 키 인증 확인"""
        global client_id, client_secret, CUSTOMER_ID, ACCESS_LICENSE, SECRET_KEY
        
        input_client_id = self.settings_client_id.text().strip()
        input_client_secret = self.settings_client_secret.text().strip()
        
        if not input_client_id or not input_client_secret:
            QMessageBox.warning(self, "입력 오류", "Client ID와 Client Secret을 입력하세요.")
            return
        
        # 인증 확인 중 표시
        self.verify_button.setEnabled(False)
        self.verify_button.setText("인증 확인 중...")
        QApplication.processEvents()
        
        # API 인증 확인
        is_verified = verify_naver_api(input_client_id, input_client_secret)
        
        if is_verified:
            # 인증 성공
            client_id = input_client_id
            client_secret = input_client_secret
            CUSTOMER_ID = self.settings_customer_id.text().strip()
            ACCESS_LICENSE = self.settings_access_license.text().strip()
            SECRET_KEY = self.settings_secret_key.text().strip()
            
            # 설정 저장
            if save_api_config():
                self.api_verified = True
                self.auth_status_label.setText("인증 상태: ✅ 인증 완료")
                self.auth_status_label.setStyleSheet("""
                    QLabel {
                        color: #2e7d32;
                        font-weight: bold;
                        padding: 10px;
                        background-color: #c8e6c9;
                        border-radius: 6px;
                        font-size: 10pt;
                    }
                """)
                
                # 필드 비활성화
                self.settings_client_id.setEnabled(False)
                self.settings_client_secret.setEnabled(False)
                self.settings_customer_id.setEnabled(False)
                self.settings_access_license.setEnabled(False)
                self.settings_secret_key.setEnabled(False)
                self.verify_button.setEnabled(False)
                
                QMessageBox.information(self, "인증 성공", "API 키 인증이 완료되었습니다.\n설정이 저장되었습니다.")
            else:
                QMessageBox.warning(self, "저장 실패", "인증은 성공했지만 설정 저장에 실패했습니다.")
        else:
            # 인증 실패
            self.auth_status_label.setText("인증 상태: ❌ 인증 실패")
            self.auth_status_label.setStyleSheet("""
                QLabel {
                    color: #d32f2f;
                    font-weight: bold;
                    padding: 10px;
                    background-color: #ffebee;
                    border-radius: 6px;
                    font-size: 10pt;
                }
            """)
            QMessageBox.critical(
                self, 
                "인증 실패", 
                "API 키 인증에 실패했습니다.\n\n"
                "확인 사항:\n"
                "1. Client ID와 Client Secret이 올바른지 확인하세요.\n"
                "2. 네이버 개발자 센터에서 API 키가 활성화되어 있는지 확인하세요.\n"
                "3. 인터넷 연결을 확인하세요."
            )
        
        self.verify_button.setEnabled(True)
        self.verify_button.setText("✅ API 인증 확인")
    
    def check_saved_api_config(self):
        """저장된 API 설정이 유효한지 확인"""
        global client_id, client_secret
        if client_id and client_secret:
            # 간단히 인증 확인
            if verify_naver_api(client_id, client_secret):
                self.api_verified = True
                self.auth_status_label.setText("인증 상태: ✅ 인증 완료 (저장된 설정)")
                self.auth_status_label.setStyleSheet("""
                    QLabel {
                        color: #2e7d32;
                        font-weight: bold;
                        padding: 10px;
                        background-color: #c8e6c9;
                        border-radius: 6px;
                        font-size: 10pt;
                    }
                """)
                
                # 필드 비활성화
                self.settings_client_id.setEnabled(False)
                self.settings_client_secret.setEnabled(False)
                self.settings_customer_id.setEnabled(False)
                self.settings_access_license.setEnabled(False)
                self.settings_secret_key.setEnabled(False)
                self.verify_button.setEnabled(False)
    
    def setup_rank_tracking_tab(self, parent, layout):
        """순위 추적/모니터링 탭 UI 구성"""
        bold_font = QFont()
        bold_font.setBold(True)
        
        # 설명 라벨
        info_label = QLabel("📈 특정 상품의 순위 변화를 시간별로 추적하고 그래프로 확인할 수 있습니다.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                color: #2e7d32;
                padding: 15px;
                background-color: #e8f5e9;
                border-radius: 8px;
                font-size: 10pt;
            }
        """)
        layout.addWidget(info_label)
        
        # 입력 그룹
        input_group = QGroupBox("🔍 추적 설정")
        input_layout = QVBoxLayout()
        input_layout.setSpacing(10)
        
        keyword_label = QLabel("검색어:")
        keyword_label.setFont(bold_font)
        self.tracking_keyword = QLineEdit()
        self.tracking_keyword.setPlaceholderText("예: 키보드")
        self.tracking_keyword.textChanged.connect(self.load_tracking_data)
        input_layout.addWidget(keyword_label)
        input_layout.addWidget(self.tracking_keyword)
        
        mall_label = QLabel("판매처명:")
        mall_label.setFont(bold_font)
        self.tracking_mall = QLineEdit()
        self.tracking_mall.setPlaceholderText("예: OO스토어")
        self.tracking_mall.textChanged.connect(self.load_tracking_data)
        input_layout.addWidget(mall_label)
        input_layout.addWidget(self.tracking_mall)
        
        product_label = QLabel("상품명 (선택사항):")
        product_label.setFont(bold_font)
        self.tracking_product = QLineEdit()
        self.tracking_product.setPlaceholderText("정확한 상품명을 입력하면 더 정확한 추적이 가능합니다")
        input_layout.addWidget(product_label)
        input_layout.addWidget(self.tracking_product)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 알림 설정
        alert_group = QGroupBox("🔔 알림 설정")
        alert_layout = QVBoxLayout()
        
        self.alert_enabled = QCheckBox("알림 활성화")
        self.alert_enabled.setFont(bold_font)
        alert_layout.addWidget(self.alert_enabled)
        
        alert_row = QHBoxLayout()
        alert_row.addWidget(QLabel("목표 순위:"))
        self.alert_target_rank = QSpinBox()
        self.alert_target_rank.setMinimum(1)
        self.alert_target_rank.setMaximum(1000)
        self.alert_target_rank.setValue(10)
        alert_row.addWidget(self.alert_target_rank)
        alert_row.addWidget(QLabel("위 이하 달성 시 알림"))
        alert_row.addStretch()
        alert_layout.addLayout(alert_row)
        
        alert_group.setLayout(alert_layout)
        layout.addWidget(alert_group)
        
        # 버튼
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.track_button = QPushButton("🌿 순위 체크")
        self.track_button.setFont(bold_font)
        self.track_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #4caf50);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 15px 30px;
                font-weight: bold;
                font-size: 11pt;
            }
        """)
        self.track_button.clicked.connect(self.start_rank_tracking)
        button_layout.addWidget(self.track_button)
        
        self.clear_tracking_button = QPushButton("🗑️ 추적 데이터 초기화")
        self.clear_tracking_button.setFont(bold_font)
        self.clear_tracking_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ef5350, stop:1 #e53935);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 15px 30px;
                font-weight: bold;
                font-size: 11pt;
            }
        """)
        self.clear_tracking_button.clicked.connect(self.clear_tracking_data)
        button_layout.addWidget(self.clear_tracking_button)
        
        layout.addLayout(button_layout)
        
        # 상태 표시
        self.tracking_status = QLabel("")
        self.tracking_status.setStyleSheet("""
            QLabel {
                font-weight: bold;
                padding: 10px;
                background-color: #e8f5e9;
                border-radius: 6px;
                color: #2e7d32;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.tracking_status)
        
        # 그래프와 테이블을 좌우로 배치
        graph_table_layout = QHBoxLayout()
        
        # 왼쪽: 그래프 영역 (더 작게)
        graph_container = QWidget()
        graph_container_layout = QVBoxLayout()
        graph_container_layout.setContentsMargins(0, 0, 10, 0)
        
        graph_label = QLabel("📊 순위 추이 그래프:")
        graph_label.setFont(bold_font)
        graph_label.setStyleSheet("color: #2e7d32; font-size: 11pt; padding: 5px;")
        graph_container_layout.addWidget(graph_label)
        
        # Matplotlib 그래프 (더 작게)
        self.tracking_figure = Figure(figsize=(5, 3))
        self.tracking_canvas = FigureCanvas(self.tracking_figure)
        self.tracking_canvas.setFixedSize(400, 250)  # 고정 크기로 설정
        self.tracking_ax = self.tracking_figure.add_subplot(111)
        
        # 한글 폰트 설정
        try:
            self.tracking_ax.set_xlabel("체크 횟수", fontsize=8, fontfamily='Malgun Gothic')
            self.tracking_ax.set_ylabel("순위", fontsize=8, fontfamily='Malgun Gothic')
            self.tracking_ax.set_title("순위 추이", fontsize=10, fontweight='bold', fontfamily='Malgun Gothic')
        except:
            self.tracking_ax.set_xlabel("체크 횟수", fontsize=8)
            self.tracking_ax.set_ylabel("순위", fontsize=8)
            self.tracking_ax.set_title("순위 추이", fontsize=10, fontweight='bold')
        
        self.tracking_ax.grid(True, alpha=0.3)
        self.tracking_figure.tight_layout()
        graph_container_layout.addWidget(self.tracking_canvas)
        graph_container.setLayout(graph_container_layout)
        graph_table_layout.addWidget(graph_container)
        
        # 오른쪽: 추적 데이터 테이블 (더 많은 공간)
        table_container = QWidget()
        table_container_layout = QVBoxLayout()
        table_container_layout.setContentsMargins(10, 0, 0, 0)
        
        table_label = QLabel("📋 추적 이력:")
        table_label.setFont(bold_font)
        table_label.setStyleSheet("color: #2e7d32; font-size: 11pt; padding: 5px;")
        table_container_layout.addWidget(table_label)
        
        self.tracking_table = QTableWidget()
        self.tracking_table.setColumnCount(4)
        self.tracking_table.setHorizontalHeaderLabels(["날짜/시간", "순위", "상품명", "가격"])
        self.tracking_table.verticalHeader().setVisible(False)
        
        header = self.tracking_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self.tracking_table.setAlternatingRowColors(True)
        self.tracking_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tracking_table.setMinimumHeight(250)
        self.tracking_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        table_container_layout.addWidget(self.tracking_table)
        table_container.setLayout(table_container_layout)
        graph_table_layout.addWidget(table_container, stretch=1)  # 테이블에 더 많은 공간 할당
        
        layout.addLayout(graph_table_layout)
        
        # 추적 데이터 로드
        self.load_tracking_data()
    
    def setup_competitor_analysis_tab(self, parent, layout):
        """경쟁사 분석 탭 UI 구성"""
        bold_font = QFont()
        bold_font.setBold(True)
        
        # 설명 라벨
        info_label = QLabel(
            "⚔️ 입력한 판매처의 상품 순위 주변 경쟁사 상품들을 분석합니다.\n"
            "판매처를 입력하면 해당 판매처 상품 주변의 경쟁사 상품 약 10개가 표시됩니다."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                color: #2e7d32;
                padding: 15px;
                background-color: #e8f5e9;
                border-radius: 8px;
                font-size: 10pt;
            }
        """)
        layout.addWidget(info_label)
        
        # 입력 그룹
        input_group = QGroupBox("🔍 분석 설정")
        input_layout = QVBoxLayout()
        input_layout.setSpacing(10)
        
        keyword_label = QLabel("검색어:")
        keyword_label.setFont(bold_font)
        self.competitor_keyword = QLineEdit()
        self.competitor_keyword.setPlaceholderText("예: 키보드")
        input_layout.addWidget(keyword_label)
        input_layout.addWidget(self.competitor_keyword)
        
        mall_label = QLabel("판매처명:")
        mall_label.setFont(bold_font)
        self.competitor_malls = QLineEdit()
        self.competitor_malls.setPlaceholderText("예: 마인드셋 공식몰")
        input_layout.addWidget(mall_label)
        input_layout.addWidget(self.competitor_malls)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 버튼
        self.analyze_button = QPushButton("⚔️ 경쟁사 분석 시작")
        self.analyze_button.setFont(bold_font)
        self.analyze_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #66bb6a, stop:1 #4caf50);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 15px 30px;
                font-weight: bold;
                font-size: 11pt;
            }
        """)
        self.analyze_button.clicked.connect(self.start_competitor_analysis)
        layout.addWidget(self.analyze_button)
        
        # 진행률
        self.competitor_progress = QProgressBar()
        self.competitor_progress.setVisible(False)
        layout.addWidget(self.competitor_progress)
        
        self.competitor_status = QLabel("")
        self.competitor_status.setStyleSheet("""
            QLabel {
                font-weight: bold;
                padding: 10px;
                background-color: #e8f5e9;
                border-radius: 6px;
                color: #2e7d32;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.competitor_status)
        
        # 비교 결과 테이블
        result_label = QLabel("📊 경쟁사 비교 결과:")
        result_label.setFont(bold_font)
        result_label.setStyleSheet("color: #2e7d32; font-size: 12pt; padding: 5px;")
        layout.addWidget(result_label)
        
        self.competitor_table = QTableWidget()
        self.competitor_table.setColumnCount(4)
        self.competitor_table.setHorizontalHeaderLabels(["판매처", "순위", "상품명", "가격"])
        self.competitor_table.verticalHeader().setVisible(False)
        
        header = self.competitor_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self.competitor_table.setAlternatingRowColors(True)
        self.competitor_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.competitor_table)
    
    def check_status_after_init(self):
        """GUI가 표시된 후에 상태 체크"""
        pass

    def animate_status(self):
        dots = self.dots[self.dot_index]
        self.label_status.setText(f"🔄 검색 중{dots} {self.progress_bar.value()}% 완료")
        self.dot_index = (self.dot_index + 1) % len(self.dots)

    def start_check(self):
        # 기존 Worker가 실행 중이면 중지
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        
        self.keywords = [k.strip() for k in self.input_keywords.toPlainText().split(",") if k.strip()]
        self.mall_name = self.input_mall.text().strip()

        if not self.keywords or not self.mall_name:
            QMessageBox.warning(self, "입력 오류", "검색어와 판매처명을 모두 입력하세요.")
            return

        if len(self.keywords) > 10:
            QMessageBox.warning(self, "제한 초과", "검색어는 최대 10개까지 가능합니다.")
            return

        self.result_display.clear()
        self.progress_bar.setValue(0)
        self.label_status.setText("🔄 검색 중")
        self.dot_index = 0
        self.status_timer.start(300)

        self.worker = Worker(self.keywords, self.mall_name)
        self.worker.result_ready.connect(self.append_result)
        self.worker.progress_update.connect(self.update_status)
        self.worker.finished_all.connect(lambda results: self.on_search_completed(results))
        self.worker.finished_all.connect(lambda _: self.status_timer.stop())
        self.button_excel.setEnabled(False)  # 검색 시작 시 버튼 비활성화
        self.worker.start()

    def append_result(self, html):
        self.result_display.append(html)

    def update_status(self, percent, keyword):
        self.progress_bar.setValue(percent)
        if percent == 100:
            self.status_timer.stop()
            self.label_status.setText("✅ 검색 완료")
    
    def on_search_completed(self, results):
        """검색 완료 후 엑셀 다운로드 버튼 활성화"""
        self.main_results = results
        self.button_excel.setEnabled(True)
    
    def download_main_excel(self):
        """메인 탭 결과를 엑셀로 다운로드"""
        if not hasattr(self, 'main_results') or not self.main_results:
            QMessageBox.warning(self, "데이터 없음", "먼저 순위 확인을 실행하세요.")
            return
        
        # 파일 저장 대화상자
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "엑셀 파일 저장",
            f"순위확인결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if not filename:
            return
        
        try:
            # 데이터 준비
            excel_data = []
            for keyword, result in self.main_results.items():
                if isinstance(result, dict) and result != "검색 결과 없음":
                    excel_data.append({
                        "검색어": keyword,
                        "순위": result.get("rank", ""),
                        "상품명": result.get("title", ""),
                        "판매처": result.get("mallName", ""),
                        "브랜드": result.get("brand", "") if result.get("brand") else "",
                        "상품타입": result.get("category", "") if result.get("category") else "",
                        "가격": int(result.get("price", 0)) if result.get("price") else 0,
                        "링크": result.get("link", "")
                    })
                else:
                    excel_data.append({
                        "검색어": keyword,
                        "순위": "",
                        "상품명": "검색 결과 없음",
                        "판매처": "",
                        "브랜드": "",
                        "상품타입": "",
                        "가격": 0,
                        "링크": ""
                    })
            
            # DataFrame 생성
            df = pd.DataFrame(excel_data)
            
            # 엑셀 저장
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='순위확인결과')
                
                # 열 너비 자동 조정
                worksheet = writer.sheets['순위확인결과']
                from openpyxl.utils import get_column_letter
                for idx, col in enumerate(df.columns, 1):
                    max_length = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    )
                    col_letter = get_column_letter(idx)
                    worksheet.column_dimensions[col_letter].width = min(max_length + 2, 50)
            
            QMessageBox.information(self, "완료", f"엑셀 파일이 저장되었습니다.\n{filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"엑셀 저장 중 오류가 발생했습니다.\n{str(e)}")
    
    def start_rank_tracking(self):
        """순위 추적 시작"""
        keyword = self.tracking_keyword.text().strip()
        mall_name = self.tracking_mall.text().strip()
        product_name = self.tracking_product.text().strip()
        
        if not keyword or not mall_name:
            QMessageBox.warning(self, "입력 오류", "검색어와 판매처명을 입력하세요.")
            return
        
        if not client_id or not client_secret:
            QMessageBox.warning(self, "API 설정 오류", "먼저 설정 탭에서 API 키를 인증하세요.")
            return
        
        self.track_button.setEnabled(False)
        self.tracking_status.setText("🔄 순위 확인 중...")
        QApplication.processEvents()
        
        # 순위 조회
        product = get_product_rank(keyword, mall_name, product_name)
        
        if product:
            # 추적 데이터 저장
            tracking_data = load_tracking_data()
            tracking_key = f"{keyword}_{mall_name}"
            
            if tracking_key not in tracking_data:
                tracking_data[tracking_key] = {
                    "keyword": keyword,
                    "mall_name": mall_name,
                    "product_name": product_name,
                    "history": []
                }
            
            # 현재 순위 기록
            record = {
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "rank": product["rank"],
                "title": product["title"],
                "price": product["price"]
            }
            
            tracking_data[tracking_key]["history"].append(record)
            save_tracking_data(tracking_data)
            
            # 알림 체크
            if self.alert_enabled.isChecked():
                target_rank = self.alert_target_rank.value()
                if product["rank"] <= target_rank:
                    QMessageBox.information(
                        self,
                        "🎉 목표 달성!",
                        f"축하합니다! 목표 순위 {target_rank}위를 달성했습니다.\n\n"
                        f"현재 순위: {product['rank']}위\n"
                        f"상품명: {product['title']}"
                    )
            
            self.tracking_status.setText(
                f"✅ 순위 확인 완료! 현재 순위: {product['rank']}위 | "
                f"상품명: {product['title'][:30]}..."
            )
        else:
            self.tracking_status.setText("❌ 검색 결과를 찾을 수 없습니다.")
            QMessageBox.warning(self, "결과 없음", "해당 조건의 상품을 찾을 수 없습니다.")
        
        self.track_button.setEnabled(True)
        
        # 그래프 및 테이블 업데이트
        self.load_tracking_data()
    
    def load_tracking_data(self):
        """추적 데이터 로드 및 표시"""
        keyword = self.tracking_keyword.text().strip()
        mall_name = self.tracking_mall.text().strip()
        
        if not keyword or not mall_name:
            return
        
        tracking_key = f"{keyword}_{mall_name}"
        tracking_data = load_tracking_data()
        
        if tracking_key not in tracking_data:
            self.tracking_table.setRowCount(0)
            self.tracking_ax.clear()
            try:
                self.tracking_ax.set_xlabel("체크 횟수", fontsize=8, fontfamily='Malgun Gothic')
                self.tracking_ax.set_ylabel("순위", fontsize=8, fontfamily='Malgun Gothic')
                self.tracking_ax.set_title("순위 추이", fontsize=10, fontweight='bold', fontfamily='Malgun Gothic')
            except:
                self.tracking_ax.set_xlabel("체크 횟수", fontsize=8)
                self.tracking_ax.set_ylabel("순위", fontsize=8)
                self.tracking_ax.set_title("순위 추이", fontsize=10, fontweight='bold')
            self.tracking_ax.grid(True, alpha=0.3)
            self.tracking_canvas.draw()
            return
        
        history = tracking_data[tracking_key]["history"]
        
        if not history:
            return
        
        # 테이블 업데이트
        self.tracking_table.setRowCount(len(history))
        for i, record in enumerate(history):
            self.tracking_table.setItem(i, 0, QTableWidgetItem(record["datetime"]))
            self.tracking_table.setItem(i, 1, QTableWidgetItem(str(record["rank"])))
            self.tracking_table.setItem(i, 2, QTableWidgetItem(record["title"][:50]))
            self.tracking_table.setItem(i, 3, QTableWidgetItem(f"{record['price']:,}원"))
        
        # 그래프 업데이트
        self.tracking_ax.clear()
        dates = [record["datetime"] for record in history]
        ranks = [record["rank"] for record in history]
        
        self.tracking_ax.plot(range(len(dates)), ranks, marker='o', linewidth=2, markersize=5, color='#4caf50')
        
        # 한글 폰트 설정
        try:
            self.tracking_ax.set_xlabel("체크 횟수", fontsize=8, fontfamily='Malgun Gothic')
            self.tracking_ax.set_ylabel("순위", fontsize=8, fontfamily='Malgun Gothic')
            title_text = f"{keyword}\n({mall_name})" if len(keyword) + len(mall_name) > 20 else f"순위 추이 - {keyword} ({mall_name})"
            self.tracking_ax.set_title(title_text, fontsize=10, fontweight='bold', fontfamily='Malgun Gothic')
        except:
            self.tracking_ax.set_xlabel("체크 횟수", fontsize=8)
            self.tracking_ax.set_ylabel("순위", fontsize=8)
            title_text = f"{keyword}\n({mall_name})" if len(keyword) + len(mall_name) > 20 else f"순위 추이 - {keyword} ({mall_name})"
            self.tracking_ax.set_title(title_text, fontsize=10, fontweight='bold')
        
        self.tracking_ax.grid(True, alpha=0.3)
        self.tracking_ax.invert_yaxis()  # 순위는 낮을수록 좋으므로 Y축 반전
        self.tracking_figure.tight_layout()
        self.tracking_canvas.draw()
    
    def clear_tracking_data(self):
        """추적 데이터 초기화"""
        reply = QMessageBox.question(
            self,
            "데이터 초기화",
            "모든 추적 데이터를 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if os.path.exists(RANK_TRACKING_FILE):
                os.remove(RANK_TRACKING_FILE)
            self.tracking_table.setRowCount(0)
            self.tracking_ax.clear()
            try:
                self.tracking_ax.set_xlabel("체크 횟수", fontsize=8, fontfamily='Malgun Gothic')
                self.tracking_ax.set_ylabel("순위", fontsize=8, fontfamily='Malgun Gothic')
                self.tracking_ax.set_title("순위 추이", fontsize=10, fontweight='bold', fontfamily='Malgun Gothic')
            except:
                self.tracking_ax.set_xlabel("체크 횟수", fontsize=8)
                self.tracking_ax.set_ylabel("순위", fontsize=8)
                self.tracking_ax.set_title("순위 추이", fontsize=10, fontweight='bold')
            self.tracking_ax.grid(True, alpha=0.3)
            self.tracking_canvas.draw()
            self.tracking_status.setText("🗑️ 추적 데이터가 초기화되었습니다.")
            QMessageBox.information(self, "완료", "추적 데이터가 초기화되었습니다.")
    
    def start_competitor_analysis(self):
        """경쟁사 분석 시작"""
        keyword = self.competitor_keyword.text().strip()
        mall_name = self.competitor_malls.text().strip()
        
        if not keyword or not mall_name:
            QMessageBox.warning(self, "입력 오류", "검색어와 판매처명을 입력하세요.")
            return
        
        if not client_id or not client_secret:
            QMessageBox.warning(self, "API 설정 오류", "먼저 설정 탭에서 API 키를 인증하세요.")
            return
        
        self.analyze_button.setEnabled(False)
        self.competitor_progress.setVisible(True)
        self.competitor_progress.setValue(0)
        self.competitor_status.setText("🔄 경쟁사 분석 중...")
        QApplication.processEvents()
        
        # 입력한 판매처의 상품과 주변 경쟁사 상품들 찾기
        self.competitor_progress.setValue(30)
        self.competitor_status.setText(f"🔄 {mall_name} 상품 검색 중...")
        QApplication.processEvents()
        
        target_product, competitors = get_competitor_products(keyword, mall_name, competitor_count=10)
        
        if not target_product:
            QMessageBox.warning(self, "검색 실패", f"'{mall_name}' 판매처의 상품을 찾을 수 없습니다.")
            self.competitor_progress.setValue(0)
            self.competitor_progress.setVisible(False)
            self.analyze_button.setEnabled(True)
            return
        
        # 결과 준비 (타겟 상품 + 경쟁사 상품들)
        results = []
        
        # 타겟 상품 추가 (강조 표시용)
        results.append({
            "mall": target_product["mallName"],
            "rank": target_product["rank"],
            "title": target_product["title"],
            "price": target_product["price"],
            "is_target": True
        })
        
        # 경쟁사 상품들 추가
        for comp in competitors:
            results.append({
                "mall": comp["mallName"],
                "rank": comp["rank"],
                "title": comp["title"],
                "price": comp["price"],
                "is_target": False
            })
        
        # 순위 순으로 정렬
        results.sort(key=lambda x: x["rank"])
        
        # 결과 표시
        self.competitor_table.setRowCount(len(results))
        
        # 폰트 설정
        bold_font = QFont()
        bold_font.setBold(True)
        
        for i, result in enumerate(results):
            # 판매처명
            mall_item = QTableWidgetItem(result["mall"])
            if result["is_target"]:
                mall_item.setFont(bold_font)
                mall_item.setForeground(QColor(0, 100, 0))  # 진한 녹색
            self.competitor_table.setItem(i, 0, mall_item)
            
            # 순위
            rank_item = QTableWidgetItem(str(result["rank"]))
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if result["is_target"]:
                rank_item.setFont(bold_font)
                rank_item.setForeground(QColor(0, 100, 0))  # 진한 녹색
            elif result["rank"] <= 10:
                rank_item.setForeground(QColor(0, 128, 0))  # darkGreen
            elif result["rank"] <= 50:
                rank_item.setForeground(QColor(184, 134, 11))  # darkYellow
            elif result["rank"] <= 100:
                rank_item.setForeground(QColor(255, 140, 0))  # orange
            self.competitor_table.setItem(i, 1, rank_item)
            
            # 상품명
            title_item = QTableWidgetItem(result["title"][:60] + "..." if len(result["title"]) > 60 else result["title"])
            if result["is_target"]:
                title_item.setFont(bold_font)
            self.competitor_table.setItem(i, 2, title_item)
            
            # 가격
            if result["price"] > 0:
                price_item = QTableWidgetItem(f"{result['price']:,}원")
                price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if result["is_target"]:
                    price_item.setFont(bold_font)
                self.competitor_table.setItem(i, 3, price_item)
            else:
                self.competitor_table.setItem(i, 3, QTableWidgetItem("-"))
        
        # 통계 정보 표시
        avg_price = sum(r["price"] for r in results if r["price"] > 0) / len([r for r in results if r["price"] > 0]) if results else 0
        target_price = target_product["price"]
        price_diff = avg_price - target_price if avg_price > 0 else 0
        
        status_text = (
            f"✅ 분석 완료! | "
            f"타겟: {target_product['mallName']} ({target_product['rank']}위, {target_price:,}원) | "
            f"경쟁사: {len(competitors)}개 | "
            f"평균 가격: {avg_price:,.0f}원"
        )
        if price_diff != 0:
            status_text += f" ({'+' if price_diff > 0 else ''}{price_diff:,.0f}원)"
        
        self.competitor_status.setText(status_text)
        self.competitor_progress.setValue(100)
        self.analyze_button.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RankCheckerApp()
    window.show()
    sys.exit(app.exec())

