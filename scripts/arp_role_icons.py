"""역할별 색상 아이콘 생성.

bpy.utils.previews를 사용하여 16x16 색상 사각형 아이콘을 생성한다.
UI 버튼과 트리 항목에서 icon_value로 참조한다.
"""

_ICON_SIZE = 16
_preview_collection = None


def make_icon_pixels(rgb):
    """RGB 튜플로 16x16 RGBA 픽셀 배열 생성."""
    r, g, b = rgb
    pixel = [r, g, b, 1.0]
    return pixel * (_ICON_SIZE * _ICON_SIZE)


def register():
    """역할별 색상 아이콘 프리뷰 컬렉션 생성."""
    import bpy.utils.previews

    from skeleton_detection import ROLE_COLORS

    global _preview_collection
    _preview_collection = bpy.utils.previews.new()

    for role_id, rgb in ROLE_COLORS.items():
        icon = _preview_collection.new(role_id)
        icon.icon_size = (_ICON_SIZE, _ICON_SIZE)
        icon.image_size = (_ICON_SIZE, _ICON_SIZE)
        icon.image_pixels_float[:] = make_icon_pixels(rgb)


def unregister():
    """프리뷰 컬렉션 정리."""
    import bpy.utils.previews

    global _preview_collection
    if _preview_collection is not None:
        bpy.utils.previews.remove(_preview_collection)
        _preview_collection = None


def get_icon_id(role_id):
    """역할 ID로 아이콘 ID 반환. 등록 전이면 0."""
    if _preview_collection is None:
        return 0
    icon = _preview_collection.get(role_id)
    return icon.icon_id if icon else 0
