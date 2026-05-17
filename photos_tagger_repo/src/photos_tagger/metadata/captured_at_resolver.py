from __future__ import annotations

from dataclasses import dataclass

from photos_tagger.domain import AssetDateCorrection, CapturedAtSource


@dataclass(frozen=True, slots=True)
class ResolvedCapturedAt:
    captured_at: str | None
    source: CapturedAtSource


class CapturedAtResolver:
    def resolve_base(self, taken_at_original: str | None, modified_at_fs: str | None) -> ResolvedCapturedAt:
        if taken_at_original:
            return ResolvedCapturedAt(captured_at=taken_at_original, source=CapturedAtSource.EXIF)
        if modified_at_fs:
            return ResolvedCapturedAt(captured_at=modified_at_fs, source=CapturedAtSource.FILESYSTEM)
        return ResolvedCapturedAt(captured_at=None, source=CapturedAtSource.UNKNOWN)

    def resolve_effective(
        self,
        taken_at_original: str | None,
        modified_at_fs: str | None,
        active_correction: AssetDateCorrection | None,
    ) -> ResolvedCapturedAt:
        if active_correction is not None and active_correction.is_active and active_correction.new_captured_at:
            return ResolvedCapturedAt(
                captured_at=active_correction.new_captured_at,
                source=active_correction.new_source,
            )
        return self.resolve_base(taken_at_original=taken_at_original, modified_at_fs=modified_at_fs)
