import pytest
import numpy as np
from src.models.train import FeatureFusionPipeline

@pytest.fixture
def dummy_dataset():
    # 4サンプル (2 Tear Out, 2 Riddim)
    X_dict = {
        "drums": np.random.rand(4, 8),
        "bass": np.random.rand(4, 8),
        "subbass": np.random.rand(4, 3),
        "other": np.random.rand(4, 40)
    }
    # 0=riddim, 1=tearout
    y = np.array([0, 1, 0, 1])
    return X_dict, y

def test_feature_fusion_pipeline_fit_predict(dummy_dataset):
    X_dict, y = dummy_dataset
    
    pipeline = FeatureFusionPipeline(classifier_name="xgboost")
    
    # 4件だとCV=3のキャリブレーションで最小クラス2件となりクラッシュするため
    # fit内のフォールバックが働くはず。
    pipeline.fit(X_dict, y)
    
    preds = pipeline.predict(X_dict)
    assert preds.shape == (4,)
    
    probs = pipeline.predict_proba(X_dict)
    assert probs.shape == (4, 2)
    assert np.all((probs >= 0) & (probs <= 1))

def test_feature_fusion_pipeline_single_class_error(dummy_dataset):
    X_dict, _ = dummy_dataset
    y_single = np.array([1, 1, 1, 1])
    
    pipeline = FeatureFusionPipeline(classifier_name="xgboost")
    
    with pytest.raises(SystemExit) as excinfo:
        pipeline.fit(X_dict, y_single)
        
    assert excinfo.value.code == 1
