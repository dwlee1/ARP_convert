"""어태치먼트 본 constraint mute/restore 단위 테스트 (Blender 불필요).

ARP retarget 시 root(parent=None) 어태치먼트 본의 Child Of/ARMATURE constraint가
``None.matrix_channel`` 폭발(animation.py:196)을 일으킨다. retarget 동안만 일시
mute → 직후 복원하는 helper의 동작을 검증한다.
"""

from types import SimpleNamespace

from arp_utils import mute_attachment_constraints, restore_attachment_constraints


def _constraint(ctype, mute=False):
    return SimpleNamespace(type=ctype, mute=mute)


def _pose_bone(name, parent=None, constraints=None):
    return SimpleNamespace(name=name, parent=parent, constraints=constraints or [])


def _armature(pose_bones):
    return SimpleNamespace(pose=SimpleNamespace(bones=pose_bones))


class TestMuteAttachmentConstraints:
    def test_root_bone_with_child_of_is_muted(self):
        c = _constraint("CHILD_OF", mute=False)
        food = _pose_bone("Food", parent=None, constraints=[c])
        arm = _armature([food])

        saved = mute_attachment_constraints(arm)

        assert c.mute is True
        assert len(saved) == 1
        assert saved[0][0] is c
        assert saved[0][1] is False  # prev_mute

    def test_root_bone_with_armature_constraint_is_muted(self):
        c = _constraint("ARMATURE", mute=False)
        attach = _pose_bone("Hat", parent=None, constraints=[c])

        saved = mute_attachment_constraints(_armature([attach]))

        assert c.mute is True
        assert len(saved) == 1

    def test_non_root_bone_is_skipped(self):
        # 부모가 있으면 ARP가 정상 평가하므로 건드리지 않음
        parent = _pose_bone("spine")
        c = _constraint("CHILD_OF", mute=False)
        child = _pose_bone("hand_attach", parent=parent, constraints=[c])

        saved = mute_attachment_constraints(_armature([parent, child]))

        assert c.mute is False
        assert saved == []

    def test_already_muted_constraint_is_not_in_saved(self):
        # 사용자가 이미 꺼둔 것은 건드리지 않음 (복원 시 다시 켜지면 안 됨)
        c = _constraint("CHILD_OF", mute=True)
        bone = _pose_bone("Food", parent=None, constraints=[c])

        saved = mute_attachment_constraints(_armature([bone]))

        assert saved == []
        assert c.mute is True  # 그대로

    def test_irrelevant_constraint_types_are_ignored(self):
        # COPY_ROTATION/IK 등은 logical parent를 만들지 않으므로 무시
        c1 = _constraint("COPY_ROTATION", mute=False)
        c2 = _constraint("IK", mute=False)
        c3 = _constraint("LIMIT_ROTATION", mute=False)
        bone = _pose_bone("root_bone", parent=None, constraints=[c1, c2, c3])

        saved = mute_attachment_constraints(_armature([bone]))

        assert saved == []
        assert all(not c.mute for c in [c1, c2, c3])

    def test_mixed_constraints_only_mute_attachment_types(self):
        ca = _constraint("COPY_ROTATION", mute=False)
        cb = _constraint("CHILD_OF", mute=False)
        cc = _constraint("LIMIT_LOCATION", mute=False)
        bone = _pose_bone("Food", parent=None, constraints=[ca, cb, cc])

        saved = mute_attachment_constraints(_armature([bone]))

        assert ca.mute is False
        assert cb.mute is True
        assert cc.mute is False
        assert len(saved) == 1
        assert saved[0][0] is cb

    def test_empty_armature_returns_empty(self):
        saved = mute_attachment_constraints(_armature([]))
        assert saved == []


class TestRestoreAttachmentConstraints:
    def test_restore_returns_to_previous_state(self):
        c = _constraint("CHILD_OF", mute=False)
        bone = _pose_bone("Food", parent=None, constraints=[c])

        saved = mute_attachment_constraints(_armature([bone]))
        assert c.mute is True
        restore_attachment_constraints(saved)
        assert c.mute is False

    def test_restore_preserves_originally_muted(self):
        # 처음부터 muted였던 것은 mute_attachment에서 saved에 안 들어가니
        # restore 후에도 muted 그대로 유지
        c1 = _constraint("CHILD_OF", mute=False)
        c2 = _constraint("CHILD_OF", mute=True)
        bone1 = _pose_bone("Food", parent=None, constraints=[c1])
        bone2 = _pose_bone("Hat", parent=None, constraints=[c2])

        saved = mute_attachment_constraints(_armature([bone1, bone2]))
        restore_attachment_constraints(saved)

        assert c1.mute is False
        assert c2.mute is True

    def test_restore_handles_deleted_constraint(self):
        # retarget 도중 constraint가 삭제되면 ReferenceError가 날 수 있음 — 안전하게 무시
        class DeletedConstraint:
            @property
            def mute(self):
                raise ReferenceError("StructRNA of type Constraint has been removed")

            @mute.setter
            def mute(self, value):
                raise ReferenceError("StructRNA of type Constraint has been removed")

        saved = [(DeletedConstraint(), False)]
        # 예외 없이 통과해야 함
        restore_attachment_constraints(saved)

    def test_restore_empty_is_noop(self):
        restore_attachment_constraints([])  # 예외 없이 통과
