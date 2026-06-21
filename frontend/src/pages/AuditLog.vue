<template>
  <AppShell>
    <div class="mb-5 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-lg font-semibold text-ink-gray-9">Audit Log</h1>
        <p class="text-sm text-ink-gray-5">
          Every privileged action — who ran it, against what, and the result.
        </p>
      </div>
      <Button
        label="Refresh"
        icon-left="lucide-refresh-cw"
        :loading="audit.loading"
        @click="reload"
      />
    </div>

    <!-- Filters: action, result, and a relative date range. Wraps on mobile. -->
    <div class="mb-4 flex flex-wrap items-center gap-2">
      <Select
        v-model="filters.action"
        :options="actionOptions"
        placeholder="All actions"
      />
      <Select
        v-model="filters.result"
        :options="resultOptions"
        placeholder="All results"
      />
      <Select v-model="filters.range" :options="rangeOptions" />
      <Button
        v-if="hasFilters"
        variant="ghost"
        label="Clear"
        icon-left="lucide-x"
        @click="clearFilters"
      />
    </div>

    <ErrorState
      v-if="audit.error"
      :message="errorMessage(audit.error)"
      @retry="reload"
    />
    <div
      v-else-if="audit.loading && !rows.length"
      class="flex justify-center py-16"
    >
      <LoadingIndicator class="size-6 text-ink-gray-5" />
    </div>
    <EmptyState
      v-else-if="!rows.length"
      icon="lucide-scroll-text"
      title="No audit entries"
      :description="
        hasFilters
          ? 'No actions match these filters.'
          : 'Privileged actions will appear here as they happen.'
      "
    />
    <template v-else>
      <AuditTimeline :rows="rows" />
      <div v-if="canLoadMore" class="mt-4 flex justify-center">
        <Button label="Load more" :loading="audit.loading" @click="loadMore" />
      </div>
    </template>
  </AppShell>
</template>

<script setup>
import { Button, LoadingIndicator, Select, createResource } from "frappe-ui";
import { computed, onUnmounted, reactive, ref, watch } from "vue";
import AppShell from "@/components/AppShell.vue";
import AuditTimeline from "@/components/AuditTimeline.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import { errorMessage } from "@/utils/format";

const PAGE_SIZE = 20;
const limit = ref(PAGE_SIZE);
const filters = reactive({ action: "", result: "", range: "" });

// Action codes mirror the VPN Audit Log doctype's Select options.
const ACTIONS = [
  "provision",
  "peer_apply",
  "peer_remove",
  "interface_up",
  "interface_down",
  "sync_network",
  "reconcile",
  "status_poll",
  "keygen",
];
const actionOptions = [
  { label: "All actions", value: "" },
  ...ACTIONS.map((action) => ({ label: action.replaceAll("_", " "), value: action })),
];
const resultOptions = [
  { label: "All results", value: "" },
  { label: "success", value: "success" },
  { label: "failure", value: "failure" },
  { label: "skipped", value: "skipped" },
];
const rangeOptions = [
  { label: "Any time", value: "" },
  { label: "Last 24 hours", value: "1" },
  { label: "Last 7 days", value: "7" },
  { label: "Last 30 days", value: "30" },
];

// "N days ago" as a Frappe datetime string. The site runs UTC, so a UTC ISO
// boundary lines up with the stored `creation` timestamps.
function sinceBoundary(days) {
  const since = new Date(Date.now() - Number(days) * 86400000);
  return since.toISOString().slice(0, 19).replace("T", " ");
}

function buildFilters() {
  const conditions = [];
  if (filters.action) conditions.push(["action", "=", filters.action]);
  if (filters.result) conditions.push(["result", "=", filters.result]);
  if (filters.range)
    conditions.push(["creation", ">=", sinceBoundary(filters.range)]);
  return conditions;
}

// VPN Admin has read perm on VPN Audit Log, so the core list endpoint suffices —
// no bespoke backend endpoint (the doctype stays append-only/read-only).
const audit = createResource({
  url: "frappe.client.get_list",
  makeParams() {
    return {
      doctype: "VPN Audit Log",
      fields: [
        "name",
        "action",
        "target",
        "result",
        "actor",
        "source_ip",
        "in_use_count_at_run",
        "argv_redacted",
        "detail",
        "creation",
      ],
      filters: buildFilters(),
      order_by: "creation desc",
      limit_page_length: limit.value,
    };
  },
  auto: true,
});

const rows = computed(() => audit.data || []);
const hasFilters = computed(
  () => Boolean(filters.action || filters.result || filters.range)
);
// A full page back means there are probably more rows to fetch.
const canLoadMore = computed(() => rows.value.length >= limit.value);

function reload() {
  audit.reload();
}

function loadMore() {
  limit.value += PAGE_SIZE;
  audit.reload();
}

function clearFilters() {
  filters.action = "";
  filters.result = "";
  filters.range = "";
}

// Re-query on any filter change, resetting paging so the view starts fresh.
watch(
  () => [filters.action, filters.result, filters.range],
  () => {
    limit.value = PAGE_SIZE;
    audit.reload();
  }
);

// Keep the trail current while the page is open; cleared on unmount.
const interval = setInterval(() => audit.reload(), 30000);
onUnmounted(() => clearInterval(interval));
</script>
