import streamlit as st
import uuid
from PIL import Image, ImageFilter
import io
from supabase import create_client, Client

# ===================== 1. Supabase 配置（替换成你自己的信息） =====================
SUPABASE_URL = "afkeeqiongqqyhbxxltp"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFma2VlcWlvbmdxcXloYnh4bHRwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA5MTU1NDAsImV4cCI6MjA5NjQ5MTU0MH0.JOo0rsNfJcPSxlvUdMnCuCvMUdmN2CR1wL-G8uo_lEM"
BUCKET_NAME = "postcard-images"

# 初始化Supabase客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 初始化页面状态
if 'flip_states' not in st.session_state:
    st.session_state.flip_states = {}

# ===================== 2. 图片处理：精准马赛克 =====================
def blur_image(img: Image) -> Image:
    """仅右下角小区域模糊，不遮挡主体"""
    w, h = img.size
    box = (int(w*0.65), int(h*0.72), w, h)
    region = img.crop(box)
    region = region.filter(ImageFilter.GaussianBlur(radius=20))
    img.paste(region, box)
    return img

# 图片转字节流（用于上传云存储）
def img_to_bytes(img: Image) -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf

# ===================== 3. 页面主体 =====================
st.set_page_config(page_title="极限明信片管理", layout="wide")
st.title("📮 极限明信片管理系统（云端永久存储）")

# -------- 上传区域 --------
st.subheader("上传新明信片")
col_up1, col_up2 = st.columns(2)
front_file = col_up1.file_uploader("正面照片", type=["jpg","jpeg","png"])
back_file = col_up2.file_uploader("背面照片（自动模糊地址）", type=["jpg","jpeg","png"])

if st.button("✅ 提交保存"):
    if not front_file:
        st.error("请选择正面照片！")
    else:
        with st.spinner("正在上传至云端..."):
            card_id = str(uuid.uuid4())
            front_filename = f"{card_id}_front.jpg"
            back_filename = f"{card_id}_back.jpg"
            front_url = ""
            back_url = ""

            # 上传正面图
            try:
                img_front = Image.open(front_file)
                buf_front = img_to_bytes(img_front)
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=front_filename,
                    file=buf_front,
                    content_type="image/jpeg"
                )
                front_url = supabase.storage.from_(BUCKET_NAME).get_public_url(front_filename)
            except Exception as e:
                st.error(f"正面图上传失败：{str(e)}")
                st.stop()

            # 处理并上传背面图
            if back_file:
                try:
                    img_back = Image.open(back_file)
                    img_back_blur = blur_image(img_back)
                    buf_back = img_to_bytes(img_back_blur)
                    supabase.storage.from_(BUCKET_NAME).upload(
                        path=back_filename,
                        file=buf_back,
                        content_type="image/jpeg"
                    )
                    back_url = supabase.storage.from_(BUCKET_NAME).get_public_url(back_filename)
                except Exception as e:
                    st.error(f"背面图上传失败：{str(e)}")

            # 写入云端数据表
            data = {
                "id": card_id,
                "front_url": front_url,
                "back_url": back_url,
                "series": "未分类",
                "send_place": "未知",
                "send_time": "未知",
                "receive_place": "未知",
                "receive_time": "未知",
                "rating": 0
            }
            supabase.table("postcards").insert(data).execute()
            st.success("🎉 上传成功，数据已永久保存！")
            st.rerun()

# -------- 筛选 & 搜索区域 --------
st.divider()
st.subheader("🔍 筛选 / 搜索")
col_filter1, col_filter2, col_filter3 = st.columns(3)

# 拉取全量数据
res = supabase.table("postcards").select("*").order("id", desc=True).execute()
all_cards = res.data or []

# 提取所有系列
all_series = ["全部"]
if all_cards:
    series_set = {item["series"] for item in all_cards}
    all_series.extend(series_set)

with col_filter1:
    select_series = st.selectbox("按系列筛选", all_series)
with col_filter2:
    select_rating = st.selectbox("按评级筛选", ["全部", "0星", "1星", "2星", "3星", "4星", "5星"])
with col_filter3:
    search_text = st.text_input("关键词搜索（系列/寄出地）")

# 数据过滤
filter_cards = []
for item in all_cards:
    if select_series != "全部" and item["series"] != select_series:
        continue
    if select_rating != "全部" and item["rating"] != int(select_rating[0]):
        continue
    if search_text.strip():
        kw = search_text.lower()
        if kw not in item["series"].lower() and kw not in item["send_place"].lower():
            continue
    filter_cards.append(item)

# -------- 明信片展示区（点击切换正反面） --------
st.divider()
st.subheader("📋 明信片列表（点击按钮切换正反面）")

if not filter_cards:
    st.info("暂无匹配的明信片")
else:
    cols = st.columns(3)
    for idx, item in enumerate(filter_cards):
        card_id = item["id"]
        front_url = item["front_url"]
        back_url = item["back_url"]
        series = item["series"]
        s_place = item["send_place"]
        s_time = item["send_time"]
        r_place = item["receive_place"]
        r_time = item["receive_time"]
        rating = item["rating"]

        # 初始化翻转状态
        if card_id not in st.session_state.flip_states:
            st.session_state.flip_states[card_id] = True

        with cols[idx % 3]:
            with st.container(border=True):
                # 展示图片
                if st.session_state.flip_states[card_id]:
                    st.image(front_url, use_column_width=True)
                else:
                    if back_url:
                        st.image(back_url, use_column_width=True)
                    else:
                        st.write("无背面照片")

                # 切换按钮
                if back_url:
                    if st.button("👆 切换正反面", key=f"flip_{card_id}"):
                        st.session_state.flip_states[card_id] = not st.session_state.flip_states[card_id]
                        st.rerun()

                # 信息展示
                st.write(f"**{series}**")
                st.caption(f"评级：{rating} / 5")
                st.caption(f"寄出：{s_place} {s_time}")
                st.caption(f"收件：{r_place} {r_time}")

                # 编辑 & 删除
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
                                update_data = {
                                    "series": new_series,
                                    "rating": new_rating,
                                    "send_place": new_s_place,
                                    "send_time": new_s_time,
                                    "receive_place": new_r_place,
                                    "receive_time": new_r_time
                                }
                                supabase.table("postcards").update(update_data).eq("id", card_id).execute()
                                st.success("信息已更新！")
                                st.rerun()
                with col_btn2:
                    if st.button("🗑️ 删除", key=f"del_{card_id}"):
                        with st.spinner("删除中..."):
                            # 删除云端图片
                            if front_url:
                                supabase.storage.from_(BUCKET_NAME).remove([f"{card_id}_front.jpg"])
                            if back_url:
                                supabase.storage.from_(BUCKET_NAME).remove([f"{card_id}_back.jpg"])
                            # 删除数据表记录
                            supabase.table("postcards").delete().eq("id", card_id).execute()
                            st.success("已删除！")
                            st.rerun()
