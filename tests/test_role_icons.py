"""arp_role_icons의 픽셀 데이터 생성 로직 테스트.

bpy.utils.previews는 Blender 전용이므로 픽셀 배열 생성 함수만 테스트한다.
"""

from arp_role_icons import make_icon_pixels


def test_make_icon_pixels_length():
    """16x16 RGBA = 1024 float."""
    pixels = make_icon_pixels((1.0, 0.0, 0.0))
    assert len(pixels) == 16 * 16 * 4


def test_make_icon_pixels_color():
    """첫 픽셀이 지정 RGB + alpha 1.0인지 확인."""
    pixels = make_icon_pixels((0.5, 0.3, 0.8))
    assert pixels[0:4] == [0.5, 0.3, 0.8, 1.0]


def test_make_icon_pixels_all_same():
    """모든 픽셀이 동일 색상."""
    pixels = make_icon_pixels((0.2, 0.4, 0.6))
    for i in range(0, len(pixels), 4):
        assert pixels[i : i + 4] == [0.2, 0.4, 0.6, 1.0]
