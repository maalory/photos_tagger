from __future__ import annotations

from dataclasses import dataclass

from photos_tagger.catalog.repositories import AssetRepository, TagRepository
from photos_tagger.domain import Tag, TagScope
from photos_tagger.storage.db import DatabaseManager

SHORTCUT_KEYS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")


@dataclass(frozen=True, slots=True)
class ShortcutBinding:
    key_sequence: str
    scope: TagScope
    tag_id: int | None
    tag_name: str | None


@dataclass(frozen=True, slots=True)
class EffectiveTagItem:
    tag_id: int
    tag_name: str
    scope: TagScope


@dataclass(frozen=True, slots=True)
class AssetTagState:
    direct_tags: list[Tag]
    effective_tags: list[EffectiveTagItem]


@dataclass(frozen=True, slots=True)
class TaggingUndoAction:
    action_type: str
    asset_id: int
    tag_id: int | None
    previous_bool: bool


@dataclass(frozen=True, slots=True)
class TaggingActionResult:
    message: str
    undo_action: TaggingUndoAction | None = None


class TaggingService:
    def __init__(
        self,
        database: DatabaseManager,
        asset_repository: AssetRepository,
        tag_repository: TagRepository,
    ) -> None:
        self.database = database
        self.asset_repository = asset_repository
        self.tag_repository = tag_repository

    def list_shortcut_bindings(self) -> list[ShortcutBinding]:
        configured = {}
        for shortcut, tag in self.tag_repository.list_shortcut_bindings(scope=TagScope.ASSET):
            configured[shortcut.key_sequence] = ShortcutBinding(
                key_sequence=shortcut.key_sequence,
                scope=shortcut.scope,
                tag_id=tag.id,
                tag_name=tag.name,
            )
        return [
            configured.get(
                key,
                ShortcutBinding(
                    key_sequence=key,
                    scope=TagScope.ASSET,
                    tag_id=None,
                    tag_name=None,
                ),
            )
            for key in SHORTCUT_KEYS
        ]

    def save_shortcut_bindings(self, values: dict[str, str | None]) -> list[ShortcutBinding]:
        with self.database.connect() as conn:
            for key_sequence in SHORTCUT_KEYS:
                raw_value = values.get(key_sequence)
                name = (raw_value or "").strip()
                if name:
                    tag = self.tag_repository.get_or_create_tag(name, conn)
                    self.tag_repository.set_shortcut_binding(
                        key_sequence=key_sequence,
                        tag_id=tag.id,
                        scope=TagScope.ASSET,
                        conn=conn,
                    )
                else:
                    self.tag_repository.delete_shortcut_binding(
                        key_sequence=key_sequence,
                        scope=TagScope.ASSET,
                        conn=conn,
                    )
            conn.commit()
        return self.list_shortcut_bindings()

    def list_folder_tags(self, folder_id: int) -> list[Tag]:
        return self.tag_repository.list_folder_tags(folder_id)

    def save_folder_tags(self, folder_id: int, raw_tag_names: list[str]) -> TaggingActionResult:
        normalized_names = _normalize_tag_names(raw_tag_names)

        with self.database.connect() as conn:
            current_tags = self.tag_repository.list_folder_tags(folder_id, conn)
            current_ids = {tag.id for tag in current_tags}
            desired_tags = [self.tag_repository.get_or_create_tag(name, conn) for name in normalized_names]
            desired_ids = {tag.id for tag in desired_tags}

            for tag_id in sorted(current_ids - desired_ids):
                self.tag_repository.set_folder_tag_assignment(
                    folder_id=folder_id,
                    tag_id=tag_id,
                    is_assigned=False,
                    conn=conn,
                )

            for tag_id in sorted(desired_ids - current_ids):
                self.tag_repository.set_folder_tag_assignment(
                    folder_id=folder_id,
                    tag_id=tag_id,
                    is_assigned=True,
                    conn=conn,
                )

            conn.commit()

        if current_ids == desired_ids:
            return TaggingActionResult(message="Tagy slozky beze zmeny.")

        if desired_tags:
            return TaggingActionResult(
                message=f"Ulozeny tagy slozky: {', '.join(tag.name for tag in desired_tags)}."
            )
        return TaggingActionResult(message="Tagy slozky byly odebrany.")

    def get_asset_tag_state(self, asset_id: int) -> AssetTagState:
        direct_tags = self.tag_repository.list_direct_asset_tags(asset_id)
        effective_tags = [
            EffectiveTagItem(tag_id=tag.id, tag_name=tag.name, scope=scope)
            for tag, scope in self.tag_repository.list_effective_asset_tags(asset_id)
        ]
        return AssetTagState(direct_tags=direct_tags, effective_tags=effective_tags)

    def toggle_shortcut_tag(self, asset_id: int, key_sequence: str) -> TaggingActionResult:
        binding = self._get_shortcut_binding(key_sequence)
        if binding.tag_id is None or binding.tag_name is None:
            raise ValueError(f"Klavesa {key_sequence} nema prirazeny zadny tag.")
        return self.toggle_tag(asset_id=asset_id, tag_id=binding.tag_id, assigned_via="shortcut")

    def toggle_tag(self, asset_id: int, tag_id: int, assigned_via: str = "manual") -> TaggingActionResult:
        with self.database.connect() as conn:
            tag = self.tag_repository.get_by_id(tag_id, conn)
            if tag is None:
                raise ValueError(f"Tag s ID {tag_id} neexistuje.")

            current_ids = {item.id for item in self.tag_repository.list_direct_asset_tags(asset_id, conn)}
            was_assigned = tag.id in current_ids
            new_value = not was_assigned
            self.tag_repository.set_asset_tag_assignment(
                asset_id=asset_id,
                tag_id=tag.id,
                is_assigned=new_value,
                assigned_via=assigned_via,
                conn=conn,
            )
            conn.commit()

        action = TaggingUndoAction(
            action_type="asset_tag",
            asset_id=asset_id,
            tag_id=tag.id,
            previous_bool=was_assigned,
        )
        verb = "Pridan" if new_value else "Odebran"
        return TaggingActionResult(message=f"{verb} tag '{tag.name}'.", undo_action=action)

    def set_tag_assignment(
        self,
        asset_id: int,
        tag_id: int,
        is_assigned: bool,
        assigned_via: str = "manual",
    ) -> TaggingActionResult:
        with self.database.connect() as conn:
            tag = self.tag_repository.get_by_id(tag_id, conn)
            if tag is None:
                raise ValueError(f"Tag s ID {tag_id} neexistuje.")

            current_ids = {item.id for item in self.tag_repository.list_direct_asset_tags(asset_id, conn)}
            was_assigned = tag.id in current_ids
            if was_assigned == is_assigned:
                state_text = "pridan" if is_assigned else "odebran"
                return TaggingActionResult(message=f"Tag '{tag.name}' uz je {state_text}.")

            self.tag_repository.set_asset_tag_assignment(
                asset_id=asset_id,
                tag_id=tag.id,
                is_assigned=is_assigned,
                assigned_via=assigned_via,
                conn=conn,
            )
            conn.commit()

        action = TaggingUndoAction(
            action_type="asset_tag",
            asset_id=asset_id,
            tag_id=tag.id,
            previous_bool=was_assigned,
        )
        verb = "Pridan" if is_assigned else "Odebran"
        return TaggingActionResult(message=f"{verb} tag '{tag.name}'.", undo_action=action)

    def toggle_favorite(self, asset_id: int) -> TaggingActionResult:
        with self.database.connect() as conn:
            asset = self.asset_repository.get_by_id(asset_id, conn)
            if asset is None:
                raise ValueError(f"Asset s ID {asset_id} neexistuje.")
            new_value = not asset.is_favorite
            self.asset_repository.set_favorite(asset_id, new_value, conn)
            conn.commit()

        action = TaggingUndoAction(
            action_type="favorite",
            asset_id=asset_id,
            tag_id=None,
            previous_bool=asset.is_favorite,
        )
        text = "zapnuto" if new_value else "vypnuto"
        return TaggingActionResult(message=f"Favorite {text}.", undo_action=action)

    def toggle_rejected(self, asset_id: int) -> TaggingActionResult:
        with self.database.connect() as conn:
            asset = self.asset_repository.get_by_id(asset_id, conn)
            if asset is None:
                raise ValueError(f"Asset s ID {asset_id} neexistuje.")
            new_value = not asset.is_rejected
            self.asset_repository.set_rejected(asset_id, new_value, conn)
            conn.commit()

        action = TaggingUndoAction(
            action_type="rejected",
            asset_id=asset_id,
            tag_id=None,
            previous_bool=asset.is_rejected,
        )
        text = "zapnuto" if new_value else "vypnuto"
        return TaggingActionResult(message=f"Reject {text}.", undo_action=action)

    def undo(self, action: TaggingUndoAction) -> TaggingActionResult:
        if action.action_type == "asset_tag":
            if action.tag_id is None:
                raise ValueError("Undo pro tag vyzaduje tag_id.")
            return self.set_tag_assignment(
                asset_id=action.asset_id,
                tag_id=action.tag_id,
                is_assigned=action.previous_bool,
                assigned_via="manual",
            )

        if action.action_type == "favorite":
            return self._restore_boolean_flag(
                asset_id=action.asset_id,
                field="favorite",
                previous_value=action.previous_bool,
            )

        if action.action_type == "rejected":
            return self._restore_boolean_flag(
                asset_id=action.asset_id,
                field="rejected",
                previous_value=action.previous_bool,
            )

        raise ValueError(f"Neznamy typ undo akce: {action.action_type}")

    def _get_shortcut_binding(self, key_sequence: str) -> ShortcutBinding:
        for binding in self.list_shortcut_bindings():
            if binding.key_sequence == key_sequence:
                return binding
        raise ValueError(f"Nepodporovana klavesa: {key_sequence}")

    def _restore_boolean_flag(self, asset_id: int, field: str, previous_value: bool) -> TaggingActionResult:
        with self.database.connect() as conn:
            asset = self.asset_repository.get_by_id(asset_id, conn)
            if asset is None:
                raise ValueError(f"Asset s ID {asset_id} neexistuje.")

            if field == "favorite":
                self.asset_repository.set_favorite(asset_id, previous_value, conn)
                conn.commit()
                text = "zapnuto" if previous_value else "vypnuto"
                return TaggingActionResult(message=f"Favorite vracen na stav {text}.")

            self.asset_repository.set_rejected(asset_id, previous_value, conn)
            conn.commit()
            text = "zapnuto" if previous_value else "vypnuto"
            return TaggingActionResult(message=f"Reject vracen na stav {text}.")


def _normalize_tag_names(raw_tag_names: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_tag_names:
        name = raw_name.strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result
