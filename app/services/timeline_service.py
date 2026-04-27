from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models.domain import (
    FreelancerAvailability,
    ProjectTimeline,
    TaskDependency,
    TaskItem,
    TimelineEntry,
)
from app.services.context_bank import ContextBankService


class TimelineService:
    def __init__(self, context_bank: ContextBankService) -> None:
        self._context_bank = context_bank

    async def create_timeline(
        self,
        project_id: str,
        tasks: list[TaskItem],
        start_date: datetime | None = None,
    ) -> ProjectTimeline:
        if start_date is None:
            start_date = datetime.now(timezone.utc)

        entries: list[TimelineEntry] = []
        for task in tasks:
            entry = TimelineEntry(
                entry_id=task.task_id,
                project_id=project_id,
                entry_type="task",
                title=task.title,
                description=task.description,
                assigned_to=task.assigned_to,
                dependencies=task.dependencies,
                status="not_started",
                estimated_hours=task.estimated_hours,
            )
            entries.append(entry)
            await self._context_bank.add_timeline_entry(project_id, entry)

        scheduled_entries = await self._suggest_schedule(project_id, entries, start_date)
        critical_path = await self._calculate_critical_path(project_id, scheduled_entries)

        timeline = ProjectTimeline(
            project_id=project_id,
            entries=scheduled_entries,
            critical_path=critical_path,
        )

        return timeline

    async def get_timeline(self, project_id: str) -> ProjectTimeline | None:
        entries = await self._context_bank.get_timeline_entries(project_id)
        if not entries:
            return None

        critical_path = await self._calculate_critical_path(project_id, entries)
        return ProjectTimeline(
            project_id=project_id,
            entries=entries,
            critical_path=critical_path,
        )

    async def update_entry_status(
        self,
        project_id: str,
        entry_id: str,
        status: str,
        actual_hours: int | None = None,
    ) -> TimelineEntry | None:
        entries = await self._context_bank.get_timeline_entries(project_id)
        for entry in entries:
            if entry.entry_id == entry_id:
                entry.status = status
                entry.updated_at = datetime.now(timezone.utc)
                if actual_hours is not None:
                    entry.actual_hours = actual_hours
                await self._context_bank.add_timeline_entry(project_id, entry)
                return entry
        return None

    async def _suggest_schedule(
        self,
        project_id: str,
        entries: list[TimelineEntry],
        start_date: datetime,
    ) -> list[TimelineEntry]:
        overview = await self._context_bank.get_project_overview(project_id)
        if overview is None:
            return entries

        freelancer_map: dict[str, FreelancerAvailability] = {
            f.name: f for f in overview.freelancers
        }

        freelancer_next_available: dict[str, datetime] = defaultdict(lambda: start_date)
        entry_map: dict[str, TimelineEntry] = {e.entry_id: e for e in entries}
        scheduled: set[str] = set()
        result: list[TimelineEntry] = []

        async def schedule_entry(entry: TimelineEntry) -> TimelineEntry:
            if entry.entry_id in scheduled:
                return entry_map[entry.entry_id]

            for dep_id in entry.dependencies:
                if dep_id in entry_map and dep_id not in scheduled:
                    await schedule_entry(entry_map[dep_id])

            earliest_start = start_date
            for dep_id in entry.dependencies:
                if dep_id in entry_map:
                    dep_entry = entry_map[dep_id]
                    if dep_entry.due_date:
                        earliest_start = max(earliest_start, dep_entry.due_date)

            freelancer = entry.assigned_to
            if freelancer and freelancer in freelancer_map:
                avail = freelancer_map[freelancer]
                freelancer_next_available[freelancer] = max(
                    freelancer_next_available[freelancer],
                    earliest_start,
                )
                entry.start_date = freelancer_next_available[freelancer]
                work_days = max(1, (entry.estimated_hours + avail.hours_per_week - 1) // avail.hours_per_week) * 7
                entry.due_date = entry.start_date + timedelta(days=work_days)
                freelancer_next_available[freelancer] = entry.due_date
            else:
                entry.start_date = earliest_start
                entry.due_date = earliest_start + timedelta(days=max(1, entry.estimated_hours // 8))

            scheduled.add(entry.entry_id)
            entry_map[entry.entry_id] = entry
            return entry

        for entry in entries:
            result.append(await schedule_entry(entry))

        return result

    async def _calculate_critical_path(
        self,
        project_id: str,
        entries: list[TimelineEntry],
    ) -> list[str]:
        if not entries:
            return []

        graph: dict[str, list[str]] = defaultdict(list)
        reverse_graph: dict[str, list[str]] = defaultdict(list)
        entry_map: dict[str, TimelineEntry] = {}

        for entry in entries:
            entry_map[entry.entry_id] = entry
            for dep_id in entry.dependencies:
                graph[dep_id].append(entry.entry_id)
                reverse_graph[entry.entry_id].append(dep_id)

        in_degree: dict[str, int] = {e.entry_id: len(reverse_graph[e.entry_id]) for e in entries}
        topo_order: list[str] = []
        queue = [eid for eid, deg in in_degree.items() if deg == 0]

        while queue:
            current = queue.pop(0)
            topo_order.append(current)
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        earliest_start: dict[str, datetime] = {}
        earliest_finish: dict[str, datetime] = {}

        for eid in topo_order:
            entry = entry_map[eid]
            start = entry.start_date or datetime.now(timezone.utc)

            for dep_id in reverse_graph[eid]:
                if dep_id in earliest_finish:
                    start = max(start, earliest_finish[dep_id])

            earliest_start[eid] = start
            duration_days = max(1, (entry.estimated_hours or 0) // 8)
            earliest_finish[eid] = start + timedelta(days=duration_days)

        latest_start: dict[str, datetime] = {}
        latest_finish: dict[str, datetime] = {}
        project_end = max(earliest_finish.values()) if earliest_finish else datetime.now(timezone.utc)

        for eid in reversed(topo_order):
            entry = entry_map[eid]
            finish = latest_finish.get(eid, project_end)
            latest_finish[eid] = finish
            duration_days = max(1, (entry.estimated_hours or 0) // 8)
            latest_start[eid] = finish - timedelta(days=duration_days)

            for dep_id in reverse_graph[eid]:
                if dep_id not in latest_finish:
                    latest_finish[dep_id] = latest_start[eid]

        critical_path = [
            eid for eid in topo_order
            if earliest_start.get(eid) == latest_start.get(eid)
        ]

        return critical_path

    async def check_dependencies_met(self, project_id: str, entry_id: str) -> bool:
        entries = await self._context_bank.get_timeline_entries(project_id)
        entry_map: dict[str, TimelineEntry] = {e.entry_id: e for e in entries}

        if entry_id not in entry_map:
            return False

        entry = entry_map[entry_id]
        for dep_id in entry.dependencies:
            if dep_id in entry_map:
                if entry_map[dep_id].status != "completed":
                    return False
        return True

    async def get_blocked_entries(self, project_id: str) -> list[TimelineEntry]:
        entries = await self._context_bank.get_timeline_entries(project_id)
        blocked: list[TimelineEntry] = []

        for entry in entries:
            if entry.status == "blocked":
                blocked.append(entry)
            elif entry.status == "not_started":
                deps_met = await self.check_dependencies_met(project_id, entry.entry_id)
                if not deps_met:
                    blocked.append(entry)

        return blocked

    async def suggest_next_tasks(self, project_id: str, limit: int = 3) -> list[TimelineEntry]:
        entries = await self._context_bank.get_timeline_entries(project_id)
        candidates: list[TimelineEntry] = []

        for entry in entries:
            if entry.status == "not_started":
                deps_met = await self.check_dependencies_met(project_id, entry.entry_id)
                if deps_met:
                    candidates.append(entry)

        candidates.sort(key=lambda e: e.due_date or datetime.max.replace(tzinfo=timezone.utc))
        return candidates[:limit]
