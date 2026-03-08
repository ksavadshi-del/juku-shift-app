import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="塾シフト管理アプリ", layout="wide")
st.title("🌟 塾管理システム（時間割自動切替・連続勤務防止版）")

# --- 左側のメニュー設定 ---
st.sidebar.header("設定")
uploaded_file = st.sidebar.file_uploader("「塾管理マスタ.xlsx」をアップロードしてください", type=["xlsx"])

# 🌟 新機能：平日と休日の切り替えボタン
day_type = st.sidebar.radio("📅 今回作成するシフトの曜日", ["平日", "休日"])

# 選んだ曜日に合わせて、時間割の見出しを定義
if day_type == "平日":
    slot_mapping = {
        '①': '①15:50~17:10',
        '②': '②17:20~18:40',
        '③': '③18:50~20:10',
        '④': '④20:20~21:40'
    }
else:
    slot_mapping = {
        '①': '①13:20~14:40',
        '②': '②14:50~16:10',
        '③': '③17:20~18:40',
        '④': '④18:50~20:10' # 8:50から修正しています
    }

# 🌟 新機能：連続コマ数を計算する裏ワザ関数
def get_slot_num(s):
    s = str(s)
    if '1' in s or '①' in s: return 1
    if '2' in s or '②' in s: return 2
    if '3' in s or '③' in s: return 3
    if '4' in s or '④' in s: return 4
    return 99

if uploaded_file is not None:
    all_sheets = pd.read_excel(uploaded_file, sheet_name=None)
    
    st.header("1. データの確認・編集")
    
    df_students = all_sheets.get('生徒名簿', pd.DataFrame())
    edited_students = st.data_editor(df_students, num_rows="dynamic", key="student_editor")

    df_tutors = all_sheets.get('講師データ', pd.DataFrame())
    edited_tutors = st.data_editor(df_tutors, num_rows="dynamic", key="tutor_editor")

    st.header("2. シフト作成と保存")
    
    if st.button("✨ シフトを作成する"):
        active_students = edited_students[edited_students['状態'] == '在籍']
        
        tutor_list = []
        for _, row in edited_tutors.iterrows():
            tutor_list.append({
                '名前': row['講師名'],
                '科目': [s.strip() for s in str(row['指導可能科目']).split(',')],
                '枠': [s.strip() for s in str(row['勤務可能枠']).split(',')]
            })

        shift_results = []
        tutor_slot_count = {} 
        tutor_day_slots = {}  

        for _, student in active_students.iterrows():
            s_name = student['生徒名']
            s_sub = student['希望科目']
            # 「①」などの文字だけを抽出
            s_slot = str(student['希望枠']).strip() 
            assigned = None
            
            for t in tutor_list:
                curr_students = tutor_slot_count.get((t['名前'], s_slot), 0)
                curr_slots = tutor_day_slots.get(t['名前'], set())
                
                # 🌟 新機能：3コマ連続制限のチェック
                temp_slots = curr_slots.copy()
                temp_slots.add(s_slot)
                nums = sorted([get_slot_num(s) for s in temp_slots if get_slot_num(s) != 99])
                
                consecutive_max = 1
                current_streak = 1
                for i in range(1, len(nums)):
                    if nums[i] == nums[i-1] + 1:
                        current_streak += 1
                        if current_streak > consecutive_max:
                            consecutive_max = current_streak
                    elif nums[i] != nums[i-1]:
                        current_streak = 1
                
                # 平日の場合、4コマ連続（①②③④）になろうとしたらブロック！
                if day_type == "平日" and consecutive_max > 3:
                    rule_ok = False
                else:
                    rule_ok = True

                if (s_sub in t['科目'] and s_slot in t['枠'] and 
                    curr_students < 2 and rule_ok):
                    assigned = t['名前']
                    tutor_slot_count[(t['名前'], s_slot)] = curr_students + 1
                    curr_slots.add(s_slot)
                    tutor_day_slots[t['名前']] = curr_slots
                    break
            
            shift_results.append({'時間枠': s_slot, '担当講師': assigned or "※手配不可", '生徒名': s_name, '科目': s_sub})

        # --- 結果を時間割形式に変換 ---
        timetable = []
        tutors_in_shift = sorted(list(set([r['担当講師'] for r in shift_results if r['担当講師'] != "※手配不可"])))
        time_keys = ['①', '②', '③', '④'] # この4枠で表を作る

        for tutor in tutors_in_shift:
            row1 = {'講師名': tutor}
            row2 = {'講師名': ''}
            
            for k in time_keys:
                # 選択した曜日の正しい時間を列の名前にする
                col_name = slot_mapping.get(k, k) 
                
                students = [r for r in shift_results if r['担当講師'] == tutor and k in str(r['時間枠'])]
                
                if len(students) > 0:
                    row1[col_name] = f"{students[0]['生徒名']} ({students[0]['科目']})"
                else:
                    row1[col_name] = ""
                    
                if len(students) > 1:
                    row2[col_name] = f"{students[1]['生徒名']} ({students[1]['科目']})"
                else:
                    row2[col_name] = ""
                    
            timetable.append(row1)
            timetable.append(row2)

        df_timetable = pd.DataFrame(timetable)
        st.success(f"🎉 {day_type}のシフトを作成しました！")
        st.dataframe(df_timetable)

        # エクセル保存用のデータ作成
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            edited_students.to_excel(writer, sheet_name='生徒名簿', index=False)
            edited_tutors.to_excel(writer, sheet_name='講師データ', index=False)
            df_timetable.to_excel(writer, sheet_name='シフト表', index=False)
        
        st.download_button(
            label="📥 更新されたエクセルをダウンロード",
            data=output.getvalue(),
            file_name=f"塾管理マスタ_{day_type}_最新.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("左側のサイドバーから「塾管理マスタ.xlsx」をアップロードしてください。")