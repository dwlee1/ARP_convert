"""뷰포트 부모 체인 하이라이트 핸들러.

프리뷰 아마추어에서 본 선택 시, 선택 본 → 루트까지
부모 체인의 bone.select를 True로 설정하여 select 색상으로 표시한다.
"""

import bpy

_prev_selection = set()
_prev_active_object = None


def _parent_chain_highlight(scene, depsgraph):
    """depsgraph_update_post 핸들러."""
    global _prev_selection, _prev_active_object

    obj = bpy.context.view_layer.objects.active
    if obj is None or obj.type != "ARMATURE":
        return

    props = bpy.context.scene.arp_convert_props
    if not props.preview_armature or obj.name != props.preview_armature:
        return

    if bpy.context.mode != "POSE":
        return

    current_selection = {b.name for b in obj.data.bones if b.select}
    if current_selection == _prev_selection and obj == _prev_active_object:
        return

    _prev_selection = current_selection.copy()
    _prev_active_object = obj

    user_selected = {b.name for b in obj.data.bones if b.select}

    chain_bones = set()
    for bone_name in user_selected:
        bone = obj.data.bones.get(bone_name)
        parent = bone.parent if bone else None
        while parent:
            if parent.name in user_selected:
                break
            chain_bones.add(parent.name)
            parent = parent.parent

    for bone in obj.data.bones:
        if bone.name in user_selected:
            continue
        bone.select = bone.name in chain_bones


def register():
    """핸들러 등록."""
    if _parent_chain_highlight not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_parent_chain_highlight)


def unregister():
    """핸들러 해제."""
    global _prev_selection, _prev_active_object
    if _parent_chain_highlight in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_parent_chain_highlight)
    _prev_selection = set()
    _prev_active_object = None
