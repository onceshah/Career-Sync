"""
Enterprise Folder Planning Service.

Responsible for translating a ClassificationResult into a
provider-independent folder destination.

This service DOES NOT execute Outlook or Gmail operations.
"""

from __future__ import annotations

from app.infrastructure.config.schema import (
    FolderDefinition,
    TaxonomyConfig,
)

from app.planning.models import (
    ClassificationResult,
    FolderPlan,
    LabelPlan,
)

from app.domain.enums import FolderType


class FolderPlanningService:
    """
    Generates enterprise folder placement plans.

    Responsibilities
    ----------------
    - Resolve enterprise folders
    - Build folder paths
    - Produce FolderPlan

    Does NOT
    --------
    - Execute email moves
    - Perform AI reasoning
    - Modify classifications
    """

    def __init__(
        self,
        taxonomy: TaxonomyConfig,
    ) -> None:

        self._taxonomy = taxonomy

    def build_plan(
        self,
        classification: ClassificationResult,
        labels: LabelPlan,
    ) -> FolderPlan:
        """
        Build a provider-independent folder placement plan.
        """

        folder_type, folder = self._resolve_folder(
            classification.folder,
        )

        subfolder, exists = self._resolve_subfolder(
            classification,
        )

        path = self._build_path(
            folder,
            subfolder,
        )

        self._validate(
            folder,
            subfolder,
        )

        return FolderPlan(
            folder_type=folder_type,
            folder=folder.path,
            subfolder=subfolder,
            full_path=path,
            exists_in_taxonomy=exists,
        )

    # ---------------------------------------------------------
    # Resolution Helpers
    # ---------------------------------------------------------

    def _resolve_folder(
        self,
        folder_type: FolderType,
    ) -> tuple[FolderType, FolderDefinition]:
        """
        Resolve FolderType to a taxonomy FolderDefinition.
        """
        folder_key = folder_type.name
        folder_def = self._taxonomy.folders.get(folder_key)
        if not folder_def:
            if folder_type == FolderType.LEADS:
                return folder_type, FolderDefinition(path="Career/Leads")
            raise ValueError(f"Folder type {folder_key} not defined in taxonomy.")
        return folder_type, folder_def

    def _resolve_subfolder(
        self,
        classification: ClassificationResult,
    ) -> tuple[str | None, bool]:
        """
        Resolve an enterprise subfolder.

        Returns
        -------
        (subfolder, exists_in_taxonomy)
        """

        folder = classification.folder

        #
        # APPLICATIONS (Subfolder maps to your portfolio project name)
        #
        if folder == FolderType.APPLICATIONS:

            if classification.project is None:
                return None, True

            project_key = (
                classification.project.name
                if hasattr(classification.project, "name")
                else str(classification.project).upper().replace(" ", "_")
            )

            entity = self._taxonomy.projects.get(project_key)

            if entity:
                return entity.display_name, True

            # AI fallback
            return str(classification.project), False

        # Everything else
        return None, True
    # ---------------------------------------------------------
    # Path Builder
    # ---------------------------------------------------------

    @staticmethod
    def _build_path(
        folder: FolderDefinition,
        subfolder: str | None,
    ) -> str:
        """
        Construct a provider-independent folder path.
        """

        if subfolder:

            return (
                f"{folder.path}/{subfolder}"
            )

        return folder.path


    @staticmethod
    def _validate(
        folder,
        subfolder,
    ) -> None:
        """
        Validate the final folder destination.
        """

        if folder is None:
            raise ValueError(
                "Folder cannot be None."
            )

        if not folder.path.strip():
            raise ValueError(
                "Folder path cannot be empty."
            )

        if subfolder is not None:

            if not subfolder.strip():
                raise ValueError(
                    "Subfolder cannot be empty."
                )

            if "/" in subfolder:
                raise ValueError(
                    "Subfolder cannot contain '/'."
                )