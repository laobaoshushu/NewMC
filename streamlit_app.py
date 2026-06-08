import streamlit as st
import sqlite3
import os
import uuid
from PIL import Image, ImageFilter

# 配置
UPLOAD_FOLDER = "uploads"
DB_PATH = "postcards.db"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 初始化session状态（记录每个卡片当前显示的面）
if 'flip_states' not in st.session_state:
    st.session_state.flip_states = {}

# 初始化数据库
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

# 精准版马赛克：只模糊右下角极小区域，刚好遮地址
def blur_image(input_path, output_path):
    try:
        img = Image.open(input_path)
        w, h = img.size
        # 只模糊右下角1/4区域，精准遮地址，不浪费画面
        box = (int(w*0.6), int(h*0.7), w, h)
        region = img.crop(box)
        region = region.filter(ImageFilter.GaussianBlur(radius=20))
        img.paste(region, box)
        img.save(output_path)
        return True
    except Exception as e:
        st.warning(f"图片处理失败: {e}")
        return False

def save_file(uploaded_file, save_path):
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

# 页面布局
st.set_page_config(page_title="极限明信片管理", layout="wide")
st.title("📮 极限明信片管理系统")

# 上传区域
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

            # 处理并保存背面
            back_path = None
            if back_file:
                back_raw_name = f"{card_id}_raw.jpg"
                back_raw_path = os.path.join(UPLOAD_FOLDER, back_raw_name)
                save_file(back_file, back_raw_path)

                back_name = f"{card_id}_back.jpg"
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

# 展示&管理区域
st.divider()
st.subheader("明信片列表（点击卡片切换正反面）")
c = conn.cursor()
c.execute("SELECT * FROM postcards ORDER BY rowid DESC")
cards = c.fetchall()

if not cards:
    st.info("暂无已上传明信片")
else:
    # 瀑布流布局，一行3个卡片
    cols = st.columns(3)
    for idx, item in enumerate(cards):
        card_id, front_path, back_path, series, send_place, send_time, rec_place, rec_time, rating = item
        
        # 初始化翻转状态
        if card_id not in st.session_state.flip_states:
            st.session_state.flip_states[card_id] = True  # True=显示正面，False=显示反面
        
        with cols[idx % 3]:
            with st.container(border=True):
                # 显示当前面的图片
                if st.session_state.flip_states[card_id]:
                    if os.path.exists(front_path):
                        st.image(front_path, use_column_width=True)
                else:
                    if back_path and os.path.exists(back_path):
                        st.image(back_path, use_column_width=True)
                    else:
                        st.write("无背面照片")
                
                # 切换按钮（点击切换正反面）
                if back_path:
                    if st.button("👆 点击切换正反面", key=f"flip_{card_id}"):
                        st.session_state.flip_states[card_id] = not st.session_state.flip_states[card_id]
                        st.rerun()
                
                # 信息展示
                st.write(f"**{series}** | 评级: {rating}/5")
                st.caption(f"寄出: {send_place} {send_time}")
                st.caption(f"收件: {rec_place} {rec_time}")
                
                # 编辑&删除
                col_edit1, col_edit2 = st.columns(2)
                with col_edit1:
                    if st.button("✏️ 编辑", key=f"edit_{card_id}"):
                        with st.expander("编辑信息", expanded=True):
                            new_series = st.text_input("系列/分类", value=series, key=f"series_{card_id}")
                            new_rating = st.slider("评级", 0, 5, value=rating, key=f"rating_{card_id}")
                            new_send_place = st.text_input("寄出地", value=send_place, key=f"send_place_{card_id}")
                            new_send_time = st.text_input("寄出时间", value=send_time, key=f"send_time_{card_id}")
                            new_rec_place = st.text_input("收件地", value=rec_place, key=f"rec_place_{card_id}")
                            new_rec_time = st.text_input("收件时间", value=rec_time, key=f"rec_time_{card_id}")
                            
                            if st.button("💾 保存修改", key=f"save_{card_id}"):
                                c.execute('''
                                UPDATE postcards 
                                SET series=?, rating=?, send_place=?, send_time=?, receive_place=?, receive_time=?
                                WHERE id=?
                                ''', (new_series, new_rating, new_send_place, new_send_time, new_rec_place, new_rec_time, card_id))
                                conn.commit()
                                st.success("信息已更新！")
                                st.rerun()
                with col_edit2:
                    if st.button("🗑️ 删除", key=f"del_{card_id}"):
                        if os.path.exists(front_path):
                            os.remove(front_path)
                        if back_path and os.path.exists(back_path):
                            os.remove(back_path)
                        c.execute("DELETE FROM postcards WHERE id=?", (card_id,))
                        conn.commit()
                        st.success("已删除")
                        st.rerun()
