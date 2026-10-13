"""多模型 API 调度中心；本版所有模型请求均在此拒绝。"""
MODULE = {"id": "model_dispatch", "name": "多模型 API 调度中心", "status": "planned", "description": "未来统一处理模型选择、超时、限流和调用记录；本版关闭调用。"}


def dispatch(action: str):
    raise ValueError(f"{action} 未启用：本版仅支持离线编辑，不调用真实模型 API")
