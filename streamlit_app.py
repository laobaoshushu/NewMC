import streamlit as st
import sqlite3
import os
import uuid
from PIL import Image
import cv2
import numpy as np

# -------------------------- 配置 --------------------------
UPLOAD_FOLDER = "uploads"
DB_PATH = "postcards.db"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------------- 数据库初始化 --------------------------
@st.cache_resource
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

# -------------------------- 工具函数 --------------------------
def blur_address(image_path, output_path):
    try:
        img_cv = cv2.imread(image_path)
        if img_cv is None:
            return False
        h, w = img_cv.shape[:2]
        roi = img_cv[int(h*0.6):h, int(w*0.5):w]
        roi = cv2.GaussianBlur(roi, (31,31), 60)
        img_cv[int(h*0.6):h, int(w*0.5):w] = roi
        cv2.imwrite(output_path, img_cv)
        return True
    except Exception as e:
        st.error(f"模糊失败：{e}")
        return False

def save_uploaded_file(uploaded_file, prefix):
    file_bytes = uploaded_file.getbuffer()
    ext = uploaded_file.name.split(".")[-1]
    filename = f"{prefix}.{ext}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path

# -------------------------- 页面UI --------------------------
st.set_page_config(page_title="明信片管理", layout="wide")
st.title("📮 明信片上传与管理")

# 1. 上传区
st.subheader("上传新明信片")
col1, col2 = st.columns(2)
with col1:
    front_file = st.file_uploader("正面照片", type=["jpg","jpeg","png"])
with col2:
    back_file = st.file_uploader("背面照片（可选）", type=["jpg","jpeg","png"])

if st.button("✅ 上传并保存"):
    if not front_file:
        st.warning("请先选择正面照片")
    else:
        with st.spinner("处理中..."):
            postcard_id = str(uuid.uuid4())
            # 保存正面
            front_path = save_uploaded_file(front_file, f"{postcard_id}_front")
            # 保存并模糊背面
            back_path = None
            if back_file:
                back_raw_path = save_uploaded_file(back_file, f"{postcard_id}_back_raw")
                back_path = os.path.join(UPLOAD_FOLDER, f"{postcard_id}_back.jpg")
                blur_address(back_raw_path, back_path)
                os.remove(back_raw_path)
            # 写入数据库
            c = conn.cursor()
            c.execute('''
            INSERT INTO postcards (id, front_path, back_path)
            VALUES (?, ?, ?)
            ''', (postcard_id, front_path, back_path))
            conn.commit()
        st.success(f"上传成功！ID：{postcard_id}")
        st.rerun()

# 2. 列表展示区
st.subheader("📋 已上传明信片")
c = conn.cursor()
c.execute("SELECT * FROM postcards ORDER BY rowid DESC")
cards = c.fetchall()

if not cards:
    st.info("暂无明信片")
else:
    for card in cards:
        id_, front_path, back_path, series, send_place, send_time, receive_place, receive_time, rating = card
        with st.container(border=True):
            col1, col2, col3 = st.columns([1,1,3])
            with col1:
                if os.path.exists(front_path):
                    st.image(front_path, width=150)
            with col2:
                if back_path and os.path.exists(back_path):
                    st.image(back_path, width=150)
                else:
                    st.write("无背面")
            with col3:
                st.write(f"ID：{id_}")
                st.write(f"系列：{series} | 寄出：{send_place} {send_time}")
                if st.button("🗑️ 删除", key=f"del_{id_}"):
                    # 删除文件
                    if os.path.exists(front_path):
                        os.remove(front_path)
                    if back_path and os.path.exists(back_path):
                        os.remove(back_path)
                    # 删除数据库
                    c.execute("DELETE FROM postcards WHERE id=?", (id_,))
                    conn.commit()
                    st.success("已删除")
                    st.rerun()