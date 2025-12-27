"""
네이버 쇼핑 순위 확인 프로그램 - Streamlit 버전
"""

import streamlit as st
import os
import json
import urllib.request
import urllib.parse
import urllib.error
import re
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# API 키 저장 파일
API_CONFIG_FILE = "api_config.json"
RANK_TRACKING_FILE = "rank_tracking.json"

# 세션 상태 초기화
if 'api_verified' not in st.session_state:
    st.session_state.api_verified = False
if 'client_id' not in st.session_state:
    st.session_state.client_id = ""
if 'client_secret' not in st.session_state:
    st.session_state.client_secret = ""
if 'customer_id' not in st.session_state:
    st.session_state.customer_id = ""
if 'access_license' not in st.session_state:
    st.session_state.access_license = ""
if 'secret_key' not in st.session_state:
    st.session_state.secret_key = ""

def load_api_config():
    """저장된 API 설정 불러오기"""
    if os.path.exists(API_CONFIG_FILE):
        try:
            with open(API_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                st.session_state.client_id = config.get("client_id", "")
                st.session_state.client_secret = config.get("client_secret", "")
                st.session_state.customer_id = config.get("customer_id", "")
                st.session_state.access_license = config.get("access_license", "")
                st.session_state.secret_key = config.get("secret_key", "")
                return True
        except Exception as e:
            st.error(f"⚠️ API 설정 로드 실패: {e}")
    return False

def save_api_config():
    """API 설정 저장"""
    config = {
        "client_id": st.session_state.client_id,
        "client_secret": st.session_state.client_secret,
        "customer_id": st.session_state.customer_id,
        "access_license": st.session_state.access_license,
        "secret_key": st.session_state.secret_key
    }
    try:
        with open(API_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"⚠️ API 설정 저장 실패: {e}")
        return False

def verify_naver_api(client_id_val, client_secret_val):
    """네이버 API 인증 확인"""
    try:
        test_query = urllib.parse.quote("테스트")
        test_url = f"https://openapi.naver.com/v1/search/shop.json?query={test_query}&display=1&start=1"
        request = urllib.request.Request(test_url)
        request.add_header("X-Naver-Client-Id", client_id_val)
        request.add_header("X-Naver-Client-Secret", client_secret_val)
        response = urllib.request.urlopen(request, timeout=5)
        result = json.loads(response.read())
        return "items" in result and len(result.get("items", [])) > 0
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False
        return False
    except Exception as e:
        return False

def get_top_ranked_product_by_mall(keyword, mall_name):
    """특정 판매처의 최고 순위 상품 찾기"""
    encText = urllib.parse.quote(keyword)
    seen_titles = set()
    best_product = None
    try:
        for start in range(1, 1001, 100):
            url = f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=100&start={start}"
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", st.session_state.client_id)
            request.add_header("X-Naver-Client-Secret", st.session_state.client_secret)
            try:
                response = urllib.request.urlopen(request, timeout=10)
                result = json.loads(response.read())
                items = result.get("items", [])
                if not items:
                    break
                for idx, item in enumerate(items, start=1):
                    if item.get("mallName") and mall_name in item["mallName"]:
                        title_clean = re.sub(r"<.*?>", "", item.get("title", ""))
                        if title_clean in seen_titles:
                            continue
                        seen_titles.add(title_clean)
                        rank = start + idx - 1
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
                break
    except Exception as e:
        pass
    return best_product

def get_product_list(keyword, max_rank=100):
    """1~100위 상품 리스트 수집"""
    encText = urllib.parse.quote(keyword)
    seen_titles = set()
    products = []
    
    try:
        url = f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=100&start=1"
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id", st.session_state.client_id)
        request.add_header("X-Naver-Client-Secret", st.session_state.client_secret)
        
        response = urllib.request.urlopen(request, timeout=10)
        result = json.loads(response.read())
        items = result.get("items", [])
        
        for idx, item in enumerate(items, start=1):
            if idx > max_rank:
                break
            
            title_clean = re.sub(r"<.*?>", "", item.get("title", ""))
            if title_clean in seen_titles:
                continue
            seen_titles.add(title_clean)
            
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
            products.append(product)
    except Exception as e:
        st.error(f"오류 발생: {str(e)}")
    
    return products

def get_product_rank(keyword, mall_name, product_name=None):
    """특정 상품의 순위 조회"""
    encText = urllib.parse.quote(keyword)
    seen_titles = set()
    best_product = None
    
    try:
        for start in range(1, 1001, 100):
            url = f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=100&start={start}"
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", st.session_state.client_id)
            request.add_header("X-Naver-Client-Secret", st.session_state.client_secret)
            
            response = urllib.request.urlopen(request, timeout=10)
            result = json.loads(response.read())
            items = result.get("items", [])
            
            if not items:
                break
                
            for idx, item in enumerate(items, start=1):
                if item.get("mallName") and mall_name in item["mallName"]:
                    title_clean = re.sub(r"<.*?>", "", item.get("title", ""))
                    
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
        return None

def get_competitor_products(keyword, target_mall_name, competitor_count=10):
    """입력한 판매처 상품 주변의 경쟁사 상품들 조회"""
    encText = urllib.parse.quote(keyword)
    target_product = None
    all_products = []
    
    try:
        for start in range(1, 1001, 100):
            url = f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=100&start={start}"
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", st.session_state.client_id)
            request.add_header("X-Naver-Client-Secret", st.session_state.client_secret)
            
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
                
                if not target_product and mall_name and target_mall_name in mall_name:
                    target_product = product
                
                all_products.append(product)
        
        if not target_product:
            return None, []
        
        target_rank = target_product["rank"]
        competitors = []
        seen_malls = set()
        
        for product in all_products:
            if product["mallName"] and target_mall_name in product["mallName"]:
                continue
            
            rank_diff = abs(product["rank"] - target_rank)
            if rank_diff <= 5 and product["rank"] != target_rank:
                if product["mallName"] not in seen_malls:
                    competitors.append(product)
                    seen_malls.add(product["mallName"])
        
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
        
        competitors.sort(key=lambda x: x["rank"])
        
        return target_product, competitors[:competitor_count]
        
    except Exception as e:
        return None, []

def load_tracking_data():
    """순위 추적 데이터 불러오기"""
    if os.path.exists(RANK_TRACKING_FILE):
        try:
            with open(RANK_TRACKING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            pass
    return {}

def save_tracking_data(data):
    """순위 추적 데이터 저장"""
    try:
        with open(RANK_TRACKING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        return False

# 페이지 설정
st.set_page_config(
    page_title="네이버 순위 확인기",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 프로그램 시작 시 저장된 설정 불러오기
if not st.session_state.api_verified:
    if load_api_config():
        if st.session_state.client_id and st.session_state.client_secret:
            if verify_naver_api(st.session_state.client_id, st.session_state.client_secret):
                st.session_state.api_verified = True

# 메인 타이틀
st.title("🔍 네이버 순위 확인기")
st.markdown("---")

# 사이드바 - API 설정
with st.sidebar:
    st.header("⚙️ API 설정")
    
    client_id_input = st.text_input(
        "Client ID",
        value=st.session_state.client_id,
        type="default"
    )
    
    client_secret_input = st.text_input(
        "Client Secret",
        value=st.session_state.client_secret,
        type="password"
    )
    
    customer_id_input = st.text_input(
        "Customer ID",
        value=st.session_state.customer_id,
        type="default"
    )
    
    access_license_input = st.text_input(
        "Access License",
        value=st.session_state.access_license,
        type="default"
    )
    
    secret_key_input = st.text_input(
        "Secret Key",
        value=st.session_state.secret_key,
        type="password"
    )
    
    if st.button("✅ API 인증 확인", type="primary"):
        if client_id_input and client_secret_input:
            with st.spinner("인증 확인 중..."):
                if verify_naver_api(client_id_input, client_secret_input):
                    st.session_state.client_id = client_id_input
                    st.session_state.client_secret = client_secret_input
                    st.session_state.customer_id = customer_id_input
                    st.session_state.access_license = access_license_input
                    st.session_state.secret_key = secret_key_input
                    st.session_state.api_verified = True
                    save_api_config()
                    st.success("✅ API 인증 완료!")
                    st.rerun()
                else:
                    st.error("❌ API 인증 실패. 키를 확인하세요.")
        else:
            st.warning("Client ID와 Client Secret을 입력하세요.")
    
    if st.session_state.api_verified:
        st.success("✅ 인증 완료")
    else:
        st.warning("⚠️ API 인증 필요")

# 탭 생성
tab1, tab2, tab3, tab4, tab5 = st.tabs(["메인", "상품 리스트", "순위 추적", "경쟁사 분석", "도움말"])

# 탭 1: 메인 - 순위 확인
with tab1:
    st.header("🌿 순위 확인")
    st.markdown("검색어와 판매처명을 입력하여 순위를 확인합니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        keywords_input = st.text_area(
            "검색어 (최대 10개, 쉼표로 구분)",
            height=100,
            placeholder="예: 키보드, 마우스, 충전기"
        )
    
    with col2:
        mall_name_input = st.text_input(
            "판매처명",
            placeholder="예: OO스토어"
        )
    
    if st.button("🌿 순위 확인", type="primary"):
        if not st.session_state.api_verified:
            st.error("⚠️ 먼저 사이드바에서 API 키를 인증하세요.")
        elif not keywords_input or not mall_name_input:
            st.warning("검색어와 판매처명을 모두 입력하세요.")
        else:
            keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
            if len(keywords) > 10:
                st.warning("검색어는 최대 10개까지 가능합니다.")
            else:
                results = {}
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, keyword in enumerate(keywords):
                    status_text.text(f"검색 중: {keyword} ({i+1}/{len(keywords)})")
                    result = get_top_ranked_product_by_mall(keyword, mall_name_input)
                    if result:
                        results[keyword] = result
                    else:
                        results[keyword] = "검색 결과 없음"
                    progress_bar.progress((i+1) / len(keywords))
                
                status_text.empty()
                progress_bar.empty()
                
                # 결과 표시
                if results:
                    st.success(f"✅ {len([r for r in results.values() if r != '검색 결과 없음'])}개 검색어에 대한 결과를 찾았습니다.")
                    
                    for keyword, result in results.items():
                        with st.expander(f"🔍 {keyword}", expanded=True):
                            if isinstance(result, dict) and result != "검색 결과 없음":
                                st.markdown(f"**순위:** {result['rank']}위")
                                st.markdown(f"**상품명:** {result['title']}")
                                st.markdown(f"**판매처:** {result.get('mallName', '-')}")
                                st.markdown(f"**브랜드:** {result.get('brand', '-')}")
                                st.markdown(f"**상품타입:** {result.get('category', '-')}")
                                st.markdown(f"**가격:** {int(result['price']):,}원")
                                st.markdown(f"**링크:** [상품 보기]({result['link']})")
                            else:
                                st.error("❌ 검색 결과 없음")
                    
                    # 엑셀 다운로드
                    excel_data = []
                    for keyword, result in results.items():
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
                    
                    df = pd.DataFrame(excel_data)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    csv = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📊 엑셀 다운로드",
                        data=csv,
                        file_name=f"순위확인결과_{timestamp}.csv",
                        mime="text/csv"
                    )

# 탭 2: 상품 리스트
with tab2:
    st.header("📋 상품 리스트 추출")
    st.markdown("검색어를 입력하면 1위~100위까지의 상품 리스트를 추출합니다.")
    
    keyword_input = st.text_input("검색어", placeholder="예: 키보드, 마우스, 노트북")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        extract_button = st.button("🌿 상품 리스트 추출", type="primary")
    
    if extract_button:
        if not st.session_state.api_verified:
            st.error("⚠️ 먼저 사이드바에서 API 키를 인증하세요.")
        elif not keyword_input:
            st.warning("검색어를 입력하세요.")
        else:
            with st.spinner("상품 리스트 수집 중..."):
                products = get_product_list(keyword_input, max_rank=100)
            
            if products:
                st.success(f"✅ {len(products)}개 상품이 추출되었습니다.")
                
                # 데이터프레임으로 표시
                df = pd.DataFrame(products)
                df_display = df[["순위", "상품명", "판매처", "브랜드", "상품타입", "가격", "상품링크"]].copy()
                df_display["가격"] = df_display["가격"].apply(lambda x: f"{x:,}원")
                df_display.rename(columns={"상품타입": "카테고리", "상품링크": "링크"}, inplace=True)
                
                st.dataframe(df_display, use_container_width=True, height=400)
                
                # 엑셀 다운로드
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_keyword = re.sub(r'[<>:"/\\|?*]', '_', keyword_input)
                csv = df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📊 엑셀 다운로드",
                    data=csv,
                    file_name=f"상품리스트_{safe_keyword}_{timestamp}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("검색 결과가 없습니다.")

# 탭 3: 순위 추적
with tab3:
    st.header("📈 순위 추적")
    st.markdown("특정 상품의 순위 변화를 시간별로 추적합니다.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        tracking_keyword = st.text_input("검색어", key="track_keyword", placeholder="예: 키보드")
    
    with col2:
        tracking_mall = st.text_input("판매처명", key="track_mall", placeholder="예: OO스토어")
    
    with col3:
        tracking_product = st.text_input("상품명 (선택사항)", key="track_product", placeholder="정확한 상품명")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        track_button = st.button("🌿 순위 체크", type="primary")
    
    if track_button:
        if not st.session_state.api_verified:
            st.error("⚠️ 먼저 사이드바에서 API 키를 인증하세요.")
        elif not tracking_keyword or not tracking_mall:
            st.warning("검색어와 판매처명을 입력하세요.")
        else:
            with st.spinner("순위 확인 중..."):
                product = get_product_rank(tracking_keyword, tracking_mall, tracking_product)
            
            if product:
                # 추적 데이터 저장
                tracking_data = load_tracking_data()
                tracking_key = f"{tracking_keyword}_{tracking_mall}"
                
                if tracking_key not in tracking_data:
                    tracking_data[tracking_key] = {
                        "keyword": tracking_keyword,
                        "mall_name": tracking_mall,
                        "product_name": tracking_product,
                        "history": []
                    }
                
                record = {
                    "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "rank": product["rank"],
                    "title": product["title"],
                    "price": product["price"]
                }
                
                tracking_data[tracking_key]["history"].append(record)
                save_tracking_data(tracking_data)
                
                st.success(f"✅ 순위 확인 완료! 현재 순위: {product['rank']}위")
                st.info(f"상품명: {product['title']}")
                
                # 그래프 및 테이블 표시
                history = tracking_data[tracking_key]["history"]
                if len(history) > 1:
                    dates = [h["datetime"] for h in history]
                    ranks = [h["rank"] for h in history]
                    
                    fig, ax = plt.subplots(figsize=(10, 5))
                    ax.plot(range(len(dates)), ranks, marker='o', linewidth=2, markersize=5, color='#4caf50')
                    ax.set_xlabel("체크 횟수", fontsize=10)
                    ax.set_ylabel("순위", fontsize=10)
                    ax.set_title(f"순위 추이 - {tracking_keyword} ({tracking_mall})", fontsize=12, fontweight='bold')
                    ax.grid(True, alpha=0.3)
                    ax.invert_yaxis()
                    plt.tight_layout()
                    st.pyplot(fig)
                
                # 테이블 표시
                if history:
                    history_df = pd.DataFrame(history)
                    st.dataframe(history_df, use_container_width=True)
            else:
                st.error("❌ 검색 결과를 찾을 수 없습니다.")

# 탭 4: 경쟁사 분석
with tab4:
    st.header("⚔️ 경쟁사 분석")
    st.markdown("입력한 판매처의 상품 순위 주변 경쟁사 상품들을 분석합니다.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        competitor_keyword = st.text_input("검색어", key="comp_keyword", placeholder="예: 키보드")
    
    with col2:
        competitor_mall = st.text_input("판매처명", key="comp_mall", placeholder="예: 마인드셋 공식몰")
    
    if st.button("⚔️ 경쟁사 분석 시작", type="primary"):
        if not st.session_state.api_verified:
            st.error("⚠️ 먼저 사이드바에서 API 키를 인증하세요.")
        elif not competitor_keyword or not competitor_mall:
            st.warning("검색어와 판매처명을 입력하세요.")
        else:
            with st.spinner("경쟁사 분석 중..."):
                target_product, competitors = get_competitor_products(competitor_keyword, competitor_mall, competitor_count=10)
            
            if not target_product:
                st.error(f"'{competitor_mall}' 판매처의 상품을 찾을 수 없습니다.")
            else:
                # 결과 준비
                results = []
                results.append({
                    "판매처": target_product["mallName"],
                    "순위": target_product["rank"],
                    "상품명": target_product["title"],
                    "가격": target_product["price"],
                    "is_target": True
                })
                
                for comp in competitors:
                    results.append({
                        "판매처": comp["mallName"],
                        "순위": comp["rank"],
                        "상품명": comp["title"],
                        "가격": comp["price"],
                        "is_target": False
                    })
                
                results.sort(key=lambda x: x["순위"])
                
                # 결과 표시
                st.success(f"✅ 분석 완료! 타겟: {target_product['mallName']} ({target_product['rank']}위)")
                
                df = pd.DataFrame(results)
                df_display = df[["판매처", "순위", "상품명", "가격"]].copy()
                df_display["가격"] = df_display["가격"].apply(lambda x: f"{x:,}원" if x > 0 else "-")
                
                # 타겟 상품 강조
                st.dataframe(df_display, use_container_width=True)
                
                # 통계
                avg_price = sum(r["가격"] for r in results if r["가격"] > 0) / len([r for r in results if r["가격"] > 0]) if results else 0
                target_price = target_product["price"]
                price_diff = avg_price - target_price if avg_price > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("타겟 순위", f"{target_product['rank']}위")
                with col2:
                    st.metric("경쟁사 수", f"{len(competitors)}개")
                with col3:
                    st.metric("평균 가격", f"{avg_price:,.0f}원", f"{price_diff:+,.0f}원")

# 탭 5: 도움말
with tab5:
    st.header("📖 도움말")
    st.markdown("""
    ### 사용 방법
    
    1. **API 설정**
       - 사이드바에서 네이버 API 키를 입력하고 인증하세요.
       - API 키는 `api_config.json` 파일에 저장됩니다.
    
    2. **메인 탭**
       - 검색어(최대 10개)와 판매처명을 입력하여 순위를 확인합니다.
       - 결과를 엑셀로 다운로드할 수 있습니다.
    
    3. **상품 리스트 탭**
       - 검색어로 1~100위 상품 리스트를 추출합니다.
       - 결과를 엑셀로 다운로드할 수 있습니다.
    
    4. **순위 추적 탭**
       - 특정 상품의 순위 변화를 추적합니다.
       - 그래프로 순위 추이를 확인할 수 있습니다.
    
    5. **경쟁사 분석 탭**
       - 타겟 상품 주변의 경쟁사 상품을 분석합니다.
       - 가격 비교 및 통계를 확인할 수 있습니다.
    
    ### 주의사항
    
    - 네이버 API 사용량 제한에 주의하세요.
    - API 키는 안전하게 보관하세요.
    - 검색 결과는 실시간으로 변동될 수 있습니다.
    """)

