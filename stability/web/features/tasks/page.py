from __future__ import annotations

from .detail_page import TaskDetailPageMixin
from .forms import TaskFormsMixin
from .overview_page import TasksPageMixin

__all__ = ["TasksPageMixin", "TaskFormsMixin", "TaskDetailPageMixin"]
