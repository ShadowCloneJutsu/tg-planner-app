import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import io
from fpdf import FPDF  # pip install fpdf2

try:
    from huggingface_hub import InferenceClient  # pip install huggingface-hub

    HF_READY = True
except ImportError:
    HF_READY = False
    st.warning("huggingface-hub не установлен. Генератор идей временно недоступен.")

# Hugging Face (с обработкой)
try:
    HF_TOKEN = st.secrets["HF_TOKEN"]
    client = InferenceClient(token=HF_TOKEN) if HF_READY else None
except (KeyError, Exception) as e:
    client = None
    st.warning("HF токен не настроен. Генератор идей недоступен. Добавь HF_TOKEN в Secrets.")

# SQLite setup
DB_FILE = 'tg_data.db'


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            day_of_week TEXT,
            time TEXT,
            title TEXT,
            content_type TEXT,
            format TEXT,
            copywriter TEXT,
            reviewer TEXT,
            designer TEXT,
            chief_editor TEXT,
            status TEXT DEFAULT 'Не готов',
            published TEXT DEFAULT 'Нет'
        )
    ''')
    conn.commit()
    conn.close()


def generate_ideas(topic):
    if not client:
        return "Генератор недоступен. Настрой HF_TOKEN в Secrets."
    prompt = f'Предложи 3-5 идей для поста в TG-канале о музыке по теме "{topic}". Укажи тип (информационный/вовлекающий/развлекательный), формат (интервью/новость/общение/видео/подкаст/мемы/туториал) и краткое описание. Нумеруй варианты. Ответь только списком идей.'
    try:
        response = client.text_generation(
            prompt,
            model="mistralai/Mistral-7B-Instruct-v0.1",
            max_new_tokens=400,
            temperature=0.8,
            do_sample=True
        )
        ideas_text = response[len(prompt):].strip()
        ideas_list = [line.strip() for line in ideas_text.split('\n') if line.strip()][:5]
        return '\n'.join(ideas_list) if ideas_list else "Ошибка генерации."
    except Exception as e:
        return f"Ошибка HF: {str(e)}."


def generate_pdf(topic, ideas_text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Идеи для TG-поста: {topic}", ln=1, align='C')
    pdf.ln(10)

    y = pdf.get_y()
    for i, idea in enumerate(ideas_text.split('\n'), 1):
        pdf.cell(200, 10, txt=f"{i}. {idea.strip()}", ln=1)
        y += 10
        if y > 250:
            pdf.add_page()
            y = 10

    pdf_output = io.BytesIO()
    pdf_output.write(pdf.output(dest='S').encode('latin1'))
    pdf_output.seek(0)
    return pdf_output.getvalue()


@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM posts ORDER BY date, time", conn)
    conn.close()
    required_cols = ['date', 'day_of_week', 'time', 'title', 'content_type', 'format',
                     'copywriter', 'reviewer', 'designer', 'chief_editor', 'status', 'published']
    for col in required_cols:
        if col not in df.columns:
            df[col] = ''
    df.columns = ['ID'] + [c.capitalize().replace('_', ' ') for c in required_cols]
    return df


def add_post(date_str, time_str, title, content_type, format_str, copywriter):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    day_of_week = datetime.strptime(date_str, '%d %B %Y г.').strftime('%A')
    cursor.execute('''
        INSERT INTO posts (date, day_of_week, time, title, content_type, format, copywriter, status, published)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Не готов', 'Нет')
    ''', (date_str, day_of_week, time_str, title, content_type, format_str, copywriter))
    conn.commit()
    conn.close()


def update_post(row_id, updates):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for col, val in updates.items():
        col_map = {'Название': 'title', 'Тип контента': 'content_type', 'Формат': 'format', 'Копирайтер': 'copywriter'}
        sql_col = col_map.get(col, col.lower().replace(' ', '_'))
        cursor.execute(f"UPDATE posts SET {sql_col} = ? WHERE id = ?", (val, row_id))
    conn.commit()
    conn.close()


def update_status(row_id, status):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE posts SET status = ? WHERE id = ?", (status, row_id))
    conn.commit()
    conn.close()


def update_published(row_id, published):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE posts SET published = ? WHERE id = ?", (published, row_id))
    conn.commit()
    conn.close()


# Streamlit UI
st.set_page_config(page_title="TG Канал Планировщик", layout="wide", page_icon="🎵")

init_db()

st.title("🎵 Планировщик контента для TG-канала")
st.markdown("---")

df = load_data()

# Сайдбар для фильтров
st.sidebar.header("Фильтры")
status_filter = st.sidebar.multiselect("Статус", ['Готов', 'Не готов'], default=['Не готов'])
date_filter = st.sidebar.date_input("Дата от", value=date.today())

filtered_df = df[df['Status'].isin(status_filter)]
if 'Date' in filtered_df.columns:
    filtered_df = filtered_df[pd.to_datetime(filtered_df['Date'], errors='coerce').dt.date >= date_filter]

# Карточки постов
cols = st.columns(3)
for idx, row in filtered_df.iterrows():
    with cols[idx % 3]:
        with st.container():
            st.markdown(f"### {row.get('Title', 'Без названия')}")
            st.caption(f"📅 {row.get('Date', '')} | {row.get('Day Of Week', '')} | {row.get('Time', '')}")
            st.info(f"Тип: {row.get('Content Type', '')} | Формат: {row.get('Format', '')}")
            st.caption(
                f"👥 {row.get('Copywriter', '')} → {row.get('Reviewer', '')} → {row.get('Designer', '')} → {row.get('Chief Editor', '')}")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✏️ Правка", key=f"edit_{row.get('ID', idx)}"):
                    st.session_state.edit_row = row.get('ID')
            with col2:
                if st.button("Готов" if row.get('Status', '') == 'Не готов' else "Не готов",
                             key=f"status_{row.get('ID', idx)}"):
                    new_status = 'Готов' if row.get('Status', '') == 'Не готов' else 'Не готов'
                    update_status(row.get('ID'), new_status)
                    st.rerun()
            with col3:
                published = 'Да' if row.get('Published', '') == 'Да' else 'Нет'
                if st.button(published, key=f"pub_{row.get('ID', idx)}"):
                    new_published = 'Да' if row.get('Published', '') == 'Нет' else 'Нет'
                    update_published(row.get('ID'), new_published)
                    st.rerun()

# Правка поста
if 'edit_row' in st.session_state:
    with st.expander("Редактировать пост", expanded=True):
        row_id = st.session_state.edit_row
        row = df[df['ID'] == row_id].iloc[0]
        new_name = st.text_input("Название", value=row.get('Title', ''))
        new_type = st.selectbox("Тип контента", ['Информационный', 'Вовлекающий', 'Развлекательный'],
                                key=f"type_{row_id}")
        new_format = st.selectbox("Формат", ['Интервью', 'Новость', 'Общение', 'Видео', 'Подкаст', 'Мемы', 'Туториал'],
                                  key=f"format_{row_id}")
        new_writer = st.text_input("Копирайтер", value=row.get('Copywriter', ''))
        new_reviewer = st.text_input("Ревизор", value=row.get('Reviewer', ''))
        new_designer = st.text_input("Дизайнер", value=row.get('Designer', ''))
        new_chief = st.text_input("Глав. ред.", value=row.get('Chief Editor', ''))
        if st.button("Сохранить правки"):
            updates = {'Название': new_name, 'Тип контента': new_type, 'Формат': new_format, 'Копирайтер': new_writer,
                       'Ревизор': new_reviewer, 'Дизайнер': new_designer, 'Глав. ред.': new_chief}
            update_post(row_id, updates)
            st.success("Сохранено!")
            del st.session_state.edit_row
            st.rerun()

# Генератор идей
st.markdown("---")
st.header("💡 Генератор идей от Hugging Face")
topic = st.text_input("Введи тему или идею (например, 'рецензия на Pharaoh')")

if 'generated_ideas' not in st.session_state:
    st.session_state.generated_ideas = None
    st.session_state.generated_topic = None

if st.button("Генерировать варианты постов"):
    if topic:
        with st.spinner("Генерирую идеи..."):
            ideas_text = generate_ideas(topic)
            st.session_state.generated_ideas = ideas_text
            st.session_state.generated_topic = topic
            st.markdown("### Предложения HF:")
            st.write(ideas_text)

            export_format = st.selectbox("Формат экспорта", ['CSV', 'PDF', 'TXT'], key="export_format")

            if st.button("📥 Скачать идеи"):
                ideas_list = [idea.strip() for idea in ideas_text.split('\n') if idea.strip()]
                safe_topic = topic.replace(' ', '_').replace('/', '_')
                filename = f"ideas_{safe_topic}.{export_format.lower()}"

                if export_format == 'CSV':
                    df_ideas = pd.DataFrame({'Тема': [topic] * len(ideas_list), 'Идея': ideas_list})
                    csv_buffer = io.StringIO()
                    df_ideas.to_csv(csv_buffer, index=False, encoding='utf-8')
                    csv_data = csv_buffer.getvalue().encode('utf-8')
                    st.download_button(label=f"Скачать {export_format}", data=csv_data, file_name=filename,
                                       mime="text/csv")

                elif export_format == 'TXT':
                    txt_content = f"Идеи для TG-поста: {topic}\n\n" + ideas_text
                    txt_data = txt_content.encode('utf-8')
                    st.download_button(label=f"Скачать {export_format}", data=txt_data, file_name=filename,
                                       mime="text/plain")

                elif export_format == 'PDF':
                    pdf_data = generate_pdf(topic, ideas_text)
                    st.download_button(label=f"Скачать {export_format}", data=pdf_data, file_name=filename,
                                       mime="application/pdf")

            if st.button("Добавить как новый пост"):
                today = datetime.now().strftime('%d %B %Y г.')
                add_post(today, '', f'Идея по "{topic}" от HF', '', '', st.session_state.get('user', ''))
                st.success("Добавлено в план!")
                st.rerun()
    else:
        st.warning("Введи тему!")

# Новый пост
st.markdown("---")
st.header("➕ Новый пост")
with st.form("new_post"):
    new_date = st.date_input("Дата")
    new_time = st.time_input("Время")
    new_name = st.text_input("Название/Идея")
    new_type = st.selectbox("Тип контента", ['Информационный', 'Вовлекающий', 'Развлекательный'])
    new_format = st.selectbox("Формат", ['Интервью', 'Новость', 'Общение', 'Видео', 'Подкаст', 'Мемы', 'Туториал'])
    new_writer = st.text_input("Копирайтер")
    new_reviewer = st.text_input("Ревизор")
    new_designer = st.text_input("Дизайнер")
    new_chief = st.text_input("Глав. ред.")
    submitted = st.form_submit_button("Добавить")
    if submitted:
        date_str = new_date.strftime('%d %B %Y г.')
        add_post(date_str, new_time.strftime('%H:%M'), new_name, new_type, new_format, new_writer)
        st.success("Добавлено!")
        st.rerun()

# Таблица всех постов
st.markdown("---")
st.header("📊 Таблица плана")
if not df.empty:
    # Стилизация для цветов (статус/опубликовано)
    def color_status(val):
        if val == 'Готов':
            return 'background-color: #d4edda'  # Зелёный
        else:
            return 'background-color: #f8d7da'  # Красный


    def color_published(val):
        if val == 'Да':
            return 'background-color: #d1ecf1'  # Синий
        else:
            return 'background-color: #fff3cd'  # Жёлтый


    styled_df = df.style.applymap(color_status, subset=['Status']).applymap(color_published, subset=['Published'])
    st.dataframe(styled_df, use_container_width=True)

    # Кнопка экспорта всей таблицы
    csv = df.to_csv(index=False, encoding='utf-8')
    st.download_button("📥 Экспорт всей таблицы в CSV", csv, "plan.csv", "text/csv")
else:
    st.info("Добавь первый пост через форму выше!")

st.markdown("---")
st.caption("Полный планировщик с таблицей. Для команды — поделитесь ссылкой!")