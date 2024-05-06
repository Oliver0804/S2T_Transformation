# %%
import os
import re
import datetime
import csv

from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P
from tqdm import tqdm
from opencc import OpenCC

import math

#檔案清單轉換為list
def find_ods_files(directory):
    ods_files = []
    for filename in os.listdir(directory):
        if filename.endswith(".ods"):
            ods_files.append(os.path.join(directory, filename))
    return ods_files
def find_csv_files(directory):
    csv_files = []
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            csv_files.append(os.path.join(directory, filename))
    # 最倒序排列
    csv_files.sort(reverse=True)
    return csv_files

def simplify_to_traditional(simplified_text):
    cc = OpenCC('s2t')  # 簡體字轉換為繁體
    return cc.convert(simplified_text)

def get_text_from_cell(cell):
    text_content = []
    for p in cell.getElementsByType(P):
        text_content.append("".join(node.data for node in p.childNodes if node.nodeType == node.TEXT_NODE))
    return "".join(text_content).strip()

def load_translation_table_from_ods(file_paths):
    translation_dict = {}
    for file_path in file_paths:
        doc = load(file_path)
        tables = doc.spreadsheet.getElementsByType(Table)
        print(f"Number of tables found: {len(tables)}")  
        for table in tables:
            rows = list(table.getElementsByType(TableRow))
            print(f"Processing {len(rows)} rows in table")  
            for row in tqdm(rows, desc="Processing rows"):
                cells = row.getElementsByType(TableCell)
                if len(cells) >= 5: 
                    simplified = get_text_from_cell(cells[4])
                    traditional = get_text_from_cell(cells[2])
                    english = get_text_from_cell(cells[1])  # 英文
                    # 簡體字轉繁體
                    traditional_simplified = simplify_to_traditional(simplified)
                    translation_dict[traditional_simplified] = {'traditional': traditional, 'english': english}
    return translation_dict


def load_translation_table_from_csv(file_paths):
    translation_dict = {}
    duplicate_count = 0  # 计数重复的词汇
    ignored_count = 0    # 计数因缺失字段而忽略的行
    for file_path in file_paths:
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            # 使用tqdm包装reader，提供进度条
            for row in tqdm(reader, desc=f"Processing {file_path}"):
                simplified = row['zh-cn'].strip()
                traditional = row['zh-tw'].strip()
                english = row['en'].strip()
                if simplified and traditional and english:
                    traditional_simplified = simplify_to_traditional(simplified)
                    if traditional_simplified in translation_dict:
                        duplicate_count += 1
                    translation_dict[traditional_simplified] = {'traditional': traditional, 'english': english}
                else:
                    ignored_count += 1
            print(f"Total rows processed in {file_path}: {reader.line_num - 1}")  # line_num 计算包括标题行在内的行数
    print(f"Duplicates found: {duplicate_count}")
    print(f"Rows ignored due to missing fields: {ignored_count}")
    return translation_dict



# %%
def replace_text(line, translation_dict, auto_mode):
    auto_replace = auto_mode
    stop_processing = False
    matches = []

    # 尋找所有可能的替換
    for simplified, details in translation_dict.items():
        start = 0
        while simplified in line[start:]:
            start = line.find(simplified, start)
            if start == -1:
                break
            end = start + len(simplified)
            matches.append((start, end, simplified, details))
            start += len(simplified)  # 避免重複檢查

    # 按起始位置和長度排序，實現最長匹配優先
    matches.sort(key=lambda x: (x[0], x[1] - x[0]), reverse=True)

    replaced_ranges = []
    for start, end, simplified, details in matches:
        if any(start >= r[0] and end <= r[1] for r in replaced_ranges):
            continue  # 如果當前詞已經在替換範圍內，則跳過

        traditional_text = details['traditional']
        traditional_choices = traditional_text.split('；')
        chosen_traditional = traditional_choices[0]  # 預設選擇第一組

        if not auto_replace:
            print(f"找到的文字: '{simplified}' 可以被替換成 '{chosen_traditional}'.")
            if len(traditional_choices) > 1:
                print(f"為 '{simplified}' 提供了多個選擇:")
                for idx, choice in enumerate(traditional_choices, 1):
                    print(f"{idx}. {choice}")
                print(f"{len(traditional_choices) + 1}. 跳過替換")
            else:
                print("只有一個選擇可用。按 Enter 鍵跳過。")
            print("輸入 'auto' 切換到自動替換模式，輸入 'stop' 停止處理。")

            user_input = input("輸入編號進行替換，'auto' 自動替換，'stop' 停止，'n' 跳過: ").strip().lower()
            if user_input == 'auto':
                auto_replace = True
                chosen_traditional = traditional_choices[0]
            elif user_input == 'stop':
                stop_processing = True
                break
            elif user_input == 'n':
                continue
            elif user_input.isdigit():
                choice_index = int(user_input) - 1
                if 0 <= choice_index < len(traditional_choices):
                    chosen_traditional = traditional_choices[choice_index]
                else:
                    print("無效的選擇，跳過替換。")
                    continue
            elif user_input == "":
                # 沒有輸入任何值，使用預設選項進行替換
                print(f"進行替換: '{simplified}' -> '{chosen_traditional}'")
            else:
                print("無效的輸入，跳過替換。")
                continue

        # 替換文字並更新替換範圍
        line = line[:start] + chosen_traditional + line[end:]
        replaced_ranges.append((start, start + len(chosen_traditional)))

    return line, auto_replace, stop_processing


# %%
# 設置ods文件路徑資料夾
directory_path = "dataset"
ods_files = find_ods_files(directory_path)
print(ods_files)
# 載入csv翻譯表資料夾
directory_path = "./wikiCGroupTools/outputData"
csv_files = find_csv_files(directory_path)
print(csv_files)

# %%
input_document = "KiCad Taipei source zh Hant.po"
output_document = "KiCad Taipei source zh Hant_translated.po"
auto_mode = False   # 自動模式
debug_mode = False  # 開啟會打印更多資訊
logging_mode = True # 如果開啟 會將有翻譯的行數與翻譯前後結果記錄於另外檔案
use_ods = False     # 使用ods文件(False: 不使用樂詞網數據)

# %%
#針對taotieren事件採用繁體字的大陸詞彙
#會將大陸詞彙轉換為繁體字的大陸詞彙的預處理
# 初始化字典
translation_dict = {}

# 加載數據
if use_ods:
    translation_dict.update(load_translation_table_from_ods(ods_files))# 加載ods文件

# 加載csv文件
translation_dict.update(load_translation_table_from_csv(csv_files))# 加載csv文件


#打印個別
# 打印translation_dict目前詞彙數量
print(f"Number of entries in translation dictionary: {len(translation_dict)}")

# %% [markdown]
# ## 抽樣打印數據100筆

# %%

# 動態計算最大長度
def format_and_trim(text, max_length):
    if len(text) > max_length:
        return text[:max_length-3] + '...'
    return text.ljust(max_length)



# 計算最大長度
max_length_english = max(len(format_and_trim(detail['english'], 30)) for detail in translation_dict.values())
max_length_simplified = max(len(format_and_trim(simplified, 20)) for simplified in translation_dict.keys())
max_length_traditional = max(len(format_and_trim(detail['traditional'], 20)) for detail in translation_dict.values())

# 打印表頭
print(f"{'English'.ljust(max_length_english)}{'Simplified'.ljust(max_length_simplified)}{'Traditional'.ljust(max_length_traditional)}")
print("-" * (max_length_english + max_length_simplified + max_length_traditional))

# 計算抽樣間隔
total_entries = len(translation_dict)
samples_to_show = 100  # 顯示條目數
step = max(1, math.ceil(total_entries / samples_to_show))

# 打印抽樣條目
for index, (simplified, details) in enumerate(translation_dict.items()):
    if index % step == 0:
        traditional = format_and_trim(details['traditional'], max_length_traditional)
        english = format_and_trim(details.get('english', ''), max_length_english)  
        simplified = format_and_trim(simplified, max_length_simplified)
        print(f"{english}{simplified}{traditional}")


# %% [markdown]
# ## 依序打印數據100比

# %%
for index, (simplified, details) in enumerate(translation_dict.items()):
    if index < 100:
        traditional = format_and_trim(details['traditional'], max_length_traditional)
        english = format_and_trim(details['english'], max_length_english)
        simplified = format_and_trim(simplified, max_length_simplified)
        print(f"{english.ljust(max_length_english)}{simplified.ljust(max_length_simplified)}{traditional.ljust(max_length_traditional)}")


# %%
def process_po_file(input_file, output_file, translation_dict, auto_mode=False, debug_mode=False, logging_mode=False):
    pattern = re.compile(r'^(msgid|msgstr)\s+"(.+?)"$')
    log_directory = "log"
    log_file_name = os.path.join(log_directory, datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".log")
    
    # 確保日誌目錄存在
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)
    
    translated_count = 0  # 計算已翻譯的詞彙
    line_number = 0  # 初始化行號變量
    log_entries = []  # 初始化日誌條目列表
    
    try:
        with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
            for line in tqdm(infile, desc="翻譯 .po 檔案"):
                line_number += 1
                if debug_mode:
                    print(f"原始行: {line.strip()}")  # 打印原始行

                match = pattern.match(line.strip())
                if match:
                    tag, original_text = match.groups()
                    translated_text, auto_mode, stop_processing = replace_text(original_text, translation_dict, auto_mode)
                    if stop_processing:
                        print("使用者選擇停止處理。")
                        break
                    newline = f'{tag} "{translated_text}"\n'
                    outfile.write(newline)

                    if original_text != translated_text:
                        translated_count += 1
                        if logging_mode:
                            log_entry = f"[{line_number}:{tag}] <{original_text}> -> <{translated_text}>\n"
                            log_entries.append(log_entry)
                    
                    if debug_mode:
                        print(f"翻譯行: {newline.strip()}")

                else:
                    outfile.write(line)
                    if debug_mode:
                        print(f"未更改行: {line.strip()}")

        if logging_mode and log_entries:
            with open(log_file_name, 'w', encoding='utf-8') as log_file:
                log_file.writelines(log_entries)

        print(f"總共翻譯了 {translated_count} 個簡體詞彙")

    except Exception as e:
        print(f"處理檔案錯誤: {e}")

# %%
process_po_file(input_document, output_document, translation_dict, auto_mode, debug_mode, logging_mode)



