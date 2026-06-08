import streamlit as st
import sqlite3
import os
import uuid
from PIL import Image, ImageFilter

# 基础配置
UPLOAD_FOLDER = "uploads"
DB_PATH = "postcards.db"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 初始化卡片翻转状态
if 'flip_states' not in st.session_state:
    st.session_state.flip_states = {}

# 数据库初始化
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS postcards (
        id TEXT PRIMARY KEY,
        front_path TEXT,
        back_path TEXT,
        series TEXT DEFAULT '未分类',
        send_place TEXT DEFAULT '未知',
        send_time TEXT DEFAULT '未知',
        receive_place TEXT DEFAULT '未知',
        receive_time TEXT DEFAULT '未知',
        rating INTEGER DEFAULT 0
    )
    ''')
    conn.commit()
    return conn

conn = init_db()

# 精准马赛克（仅右下角小区域，不遮挡主体画面）
def blur_image(input_path, output_path):
    try:
        img = Image.open(input_path)
        w, h = img.size
        # 仅右下角小范围，专门遮挡地址
        box = (int(w*0.65), int(h*0.72), w, h)
        region = img.crop(box)
        region = region.filter(ImageFilter.GaussianBlur(radius=20))
        img.paste(region, box)
        img.save(output_path)
        return True
    except Exception as e:
        st.warning(f"图片处理失败: {e}")
        return False

# 保存上传文件
def save_file(uploaded_file, save_path):
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

# 页面全局配置
st.set_page_config(page_title="极限明信片管理", layout="wide")
st.title("📮 极限明信片管理系统")

# ===================== 上传区域 =====================
st.subheader("上传新明信片")
col_up1, col_up2 = st.columns(2)
front_file = col_up1.file_uploader("正面照片", type=["jpg","jpeg","png"])
back_file = col_up2.file_uploader("背面照片（自动模糊地址）", type=["jpg","jpeg","png"])

if st.button("✅ 提交保存"):
    if not front_file:
        st.error("请选择正面照片！")
    else:
        with st.spinner("处理中..."):
            card_id = str(uuid.uuid4())
            # 保存正面
            front_name = f"{card_id}_front.jpg"
            front_path = os.path.join(UPLOAD_FOLDER, front_name)
            save_file(front_file, front_path)

            # 处理背面+马赛克
            back_path = None
            if back_file:
                back_raw_name = f"{card_id}_raw.jpg"
                back_raw_path = os.path.join(UPLOAD_FOLDER, back_raw_name)
                save_file(back_file, back_raw_path)

                back_name = f"{card_id}_back.jpg"
                back_path = os.path.join(UPLOAD_FOLDER)
                back_path = os.path.join(UPLOAD_FOLDER, back_name)
                blur_image(back_raw_path, back_path)
                os.remove(back_raw_path)

            # 写入数据库
            c = conn.cursor()
            c.execute(
                "INSERT INTO postcards (id, front_path, back_path) VALUES (?,?,?)",
                (card_id, front_path, back_path)
            )
            conn.commit()
        st.success("🎉 上传成功！")
        st.rerun()

# ===================== 筛选 & 搜索区域（新增） =====================
st.divider()
st.subheader("🔍 筛选 / 搜索")
col_filter1, col_filter2, col_filter3 = st.columns(3)

# 读取全量数据
c = conn.cursor()
c.execute("SELECT * FROM postcards ORDER BY rowid DESC")
all_cards = c.fetchall()

# 提取所有已有系列（用于下拉筛选）
all_series = ["全部"]
if all_cards:
    series_list = list({card[3] for card in all_cards})
    all_series.extend(series_list)

with col_filter1:
    select_series = st.selectbox("按系列筛选", all_series)
with col_filter2:
    select_rating = st.selectbox("按评级筛选", ["全部", "0星", "1星", "2星", "3星", "4星", "5星"])
with col_filter3:
    search_text = st.text_input("关键词搜索（系列/寄出地）")

# 过滤数据
filter_cards = []
for card in all_cards:
    c_id, f_path, b_path, series, s_place, s_time, r_place, r_time, rating = card
    # 系列过滤
    if select_series != "全部" and series != select_series:
        continue
    # 评级过滤
    if select_rating != "全部":
        target_star = int(select_rating[0])
        if rating != target_star:
            continue
    # 关键词搜索
    if search_text.strip():
        kw = search_text.lower()
        if kw not in series.lower() and kw not in s_place.lower():
            continue
    filter_cards.append(card)

# ===================== 明信片展示区（点击切换正反面） =====================
st.divider()
st.subheader("📋 明信片列表（点击按钮切换正反面）")

if not filter_cards:
    st.info("暂无匹配的明信片")
else:
    # 瀑布流：一行3列
    cols = st.columns(3)
    for idx, item in enumerate(filter_cards):
        card_id, front_path, back_path, series, s_place, s_time, r_place, r_time, rating = item

        # 初始化翻转状态
        if card_id not in st.session_state.flip_states:
            st.session_state.flip_states[card_id] = True

        with cols[idx % 3]:
            with st.container(border=True):
                # 展示图片
                if st.session_state.flip_states[card_id]:
                    if os.path.exists(front_path):
                        st.image(front_path, use_column_width=True)
                else:
                    if back_path and os.path.exists(back_path):
                        st.image(back_path, use_column_width=True)
                    else:
                        st.write("无背面照片")

                # 切换正反面按钮
                if back_path:
                    if st.button("👆 切换正反面", key=f"flip_{card_id}"):
                        st.session_state.flip_states[card_id] = not st.session_state.flip_states[card_id]
                        st.rerun()

                # 信息展示
                st.write(f"**{series}**")
                st.caption(f"评级：{rating} / 5")
                st.caption(f"寄出：{s_place} {s_time}")
                st.caption(f"收件：{r_place} {r_time}")

                # 编辑 + 删除 按钮
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✏️ 编辑", key=f"edit_{card_id}"):
                        with st.expander("编辑信息", expanded=True):
                            new_series = st.text_input("系列", value=series, key=f"ser_{card_id}")
                            new_rating = st.slider("评级", 0, 5, value=rating, key=f"rat_{card_id}")
                            new_s_place = st.text_input("寄出地", value=s_place, key=f"spl_{card_id}")
                            new_s_time = st.text_input("寄出时间", value=s_time, key=f"stm_{card_id}")
                            new_r_place = st.text_input("收件地", value=r_place, key=f"rpl_{card_id}")
                            new_r_time = st.text_input("收件时间", value=r_time, key=f"rtm_{card_id}")

                            if st.button("💾 保存", key=f"save_{card_id}"):
                                c_update = conn.cursor()
                                c_update.execute('''
                                UPDATE postcards 
                                SET series=?, rating=?, send_place=?, send_time=?, receive_place=?, receive_time=?
                                WHERE id=?
                                ''', (new_series, new_rating, new_s_place, new_s_time, new_r_place, new_r_time, card_id))
                                conn.commit()
                                st.success("信息已更新")
                                st.rerun()
                with col_btn2:
                    if st.button("🗑️ 删除", key=f"del_{card_id}"):
                        # 删除图片文件
                        if os.path.exists(front_path):
                            os.remove(front_path)
                        if back_path and os.path.exists(back_path):
                            os.remove(back_path)
                        # 删除数据库记录
                        c_del = conn.cursor()
                        c_del.execute("DELETE FROM postcards WHERE id=?", (card_id,))
                        conn.commit()
                        st.success("已删除")
                        st.rerun()
