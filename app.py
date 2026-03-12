import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import quote

st.set_page_config(
    page_title="楽天 レビューキーワード調査",
    page_icon="🔍",
    layout="wide"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def search_rakuten(keyword, num_results=20):
    """楽天市場で商品を検索し、上位商品の名前とURLを返す"""
    encoded = quote(keyword)
    url = f"https://search.rakuten.co.jp/search/mall/{encoded}/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        products = []

        # 商品ブロックを複数のセレクタで探す
        items = (
            soup.select("div.searchresultitem")
            or soup.select("div.item_box")
            or soup.select("li.item")
        )

        for item in items[:num_results]:
            # 商品タイトルリンク
            link = (
                item.select_one("h2 a")
                or item.select_one(".title a")
                or item.select_one("a.content.title")
                or item.select_one("a[href*='item.rakuten.co.jp']")
            )
            if link and link.get("href"):
                href = link["href"]
                # 楽天商品URLのみ対象
                if "item.rakuten.co.jp" in href:
                    products.append({
                        "name": link.get_text(strip=True) or "（商品名取得不可）",
                        "url": href.split("?")[0],  # クエリパラメータを除去
                    })

        return products

    except Exception as e:
        st.error(f"検索中にエラーが発生しました: {e}")
        return []


def get_reviews(product_url):
    """
    楽天商品URLからshopCode・itemCodeを抽出し、
    レビューページをスクレイピングしてレビュー文字列のリストを返す
    """
    match = re.search(r"item\.rakuten\.co\.jp/([^/]+)/([^/?#]+)", product_url)
    if not match:
        return []

    shop_code = match.group(1)
    item_code = match.group(2)

    reviews = []
    for page in range(1, 4):  # 最大3ページ（約30件）
        review_url = f"https://review.rakuten.co.jp/item/1/{shop_code}_{item_code}/{page}.1/"
        try:
            res = requests.get(review_url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            # レビュー本文要素（セレクタが変わっても対応できるよう複数用意）
            els = (
                soup.select(".revRvwUserReview")
                or soup.select("[class*='userReview']")
                or soup.select("[class*='review-body']")
                or soup.select(".review_body")
            )

            if not els:
                break  # ページが存在しない or セレクタが合わない

            for el in els:
                text = el.get_text(separator=" ", strip=True)
                if text and len(text) > 5:
                    reviews.append(text)

            time.sleep(0.6)

        except Exception:
            break

    return reviews


def find_matching_reviews(reviews, keywords):
    """指定キーワードのいずれかを含むレビューを返す（AND条件ではなくOR）"""
    matched = []
    for review in reviews:
        for kw in keywords:
            if kw in review:
                matched.append(review)
                break
    return matched


# ─────────────────────────────────────────
# UI
# ─────────────────────────────────────────

st.title("🔍 楽天 レビューキーワード調査ツール")
st.caption("楽天市場の検索上位商品から、指定キーワードを含むレビューがある商品を探します。")

st.divider()

col1, col2 = st.columns([2, 2])
with col1:
    search_keyword = st.text_input(
        "検索キーワード",
        placeholder="例: ふるさと納税 文旦",
        help="楽天市場の検索ボックスに入れるキーワード",
    )
with col2:
    filter_keywords_input = st.text_input(
        "レビューで探したいキーワード（カンマ区切り）",
        value="種,多い",
        help="このキーワードのどれかが含まれるレビューがある商品を抽出します",
    )

num_results = st.slider("取得する商品数（上位 N 件）", min_value=5, max_value=30, value=15)

run = st.button("🚀 調査開始", type="primary", use_container_width=True)

if run:
    if not search_keyword.strip():
        st.error("検索キーワードを入力してください")
        st.stop()

    keywords = [k.strip() for k in filter_keywords_input.split(",") if k.strip()]
    if not keywords:
        st.error("レビューで探したいキーワードを入力してください")
        st.stop()

    # ── Step 1: 商品検索 ──
    with st.spinner(f"「{search_keyword}」で楽天を検索中..."):
        products = search_rakuten(search_keyword, num_results)

    if not products:
        st.warning("商品が見つかりませんでした。キーワードを変えてみてください。")
        st.stop()

    st.success(f"{len(products)} 件の商品を取得しました。レビューを確認中...")

    # ── Step 2: 各商品のレビューを確認 ──
    progress_bar = st.progress(0, text="レビューを取得中...")
    rows = []

    for i, product in enumerate(products):
        progress_bar.progress((i + 1) / len(products), text=f"確認中 ({i+1}/{len(products)}): {product['name'][:30]}...")

        reviews = get_reviews(product["url"])
        matched = find_matching_reviews(reviews, keywords)

        rows.append({
            "順位": i + 1,
            "商品名": product["name"],
            "URL": product["url"],
            "レビュー取得数": len(reviews),
            f"「{'・'.join(keywords)}」含むレビュー数": len(matched),
            "該当レビュー（抜粋）": matched[0][:120] + "…" if matched else "―",
        })

        time.sleep(0.3)

    progress_bar.empty()

    df = pd.DataFrame(rows)
    keyword_col = f"「{'・'.join(keywords)}」含むレビュー数"
    matched_df = df[df[keyword_col] > 0].copy()

    # ── 結果表示 ──
    st.divider()

    tab1, tab2 = st.tabs([
        f"⚠️ キーワードあり商品 ({len(matched_df)}件)",
        f"📋 全商品一覧 ({len(products)}件)",
    ])

    with tab1:
        if matched_df.empty:
            st.success("該当する商品は見つかりませんでした。")
        else:
            st.markdown(f"**「{'・'.join(keywords)}」を含むレビューがある商品（検索順）**")
            for _, row in matched_df.iterrows():
                with st.container():
                    st.markdown(
                        f"**#{int(row['順位'])} [{row['商品名'][:60]}]({row['URL']})**  \n"
                        f"該当レビュー数: **{int(row[keyword_col])}件** ／ 取得レビュー総数: {int(row['レビュー取得数'])}件"
                    )
                    st.caption(f"📝 {row['該当レビュー（抜粋）']}")
                    st.divider()

    with tab2:
        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "URL": st.column_config.LinkColumn("URL"),
            },
        )
