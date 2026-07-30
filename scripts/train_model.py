"""
EDMサブジャンル自動判定システム — モデル学習バッチ

DBから正解ラベル(human_label)付きのデータを抽出し、
特徴量と結合して分類モデル(Tear Out vs Riddim)を学習・評価する。
"""

from src.models.train import train_and_evaluate

if __name__ == "__main__":
    train_and_evaluate()
