<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <span class="text-sm font-medium text-ink-gray-7">{{ label }}</span>
      <Button
        label="Add row"
        icon-left="lucide-plus"
        variant="ghost"
        @click="addRow"
      />
    </div>

    <EmptyState
      v-if="!rows.length"
      :title="emptyTitle"
      :description="emptyText"
      icon="lucide-list"
    />

    <div
      v-for="(row, index) in rows"
      :key="index"
      class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-3"
    >
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormControl
          v-for="col in columns"
          :key="col.key"
          v-model="row[col.key]"
          :type="col.type || 'text'"
          :label="col.label"
          :options="col.options"
          :placeholder="col.placeholder"
          :class="col.wide ? 'sm:col-span-2' : ''"
        />
      </div>
      <div class="mt-2 flex justify-end">
        <Button
          label="Remove"
          icon-left="lucide-trash-2"
          theme="red"
          variant="ghost"
          @click="removeRow(index)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { Button, FormControl } from "frappe-ui";
import EmptyState from "@/components/EmptyState.vue";

// The edited rows are the component's v-model so the parent form owns the data.
const rows = defineModel({ type: Array, default: () => [] });

const props = defineProps({
  label: { type: String, default: "" },
  // [{ key, label, type?, options?, placeholder?, wide?, default? }]
  columns: { type: Array, required: true },
  emptyTitle: { type: String, default: "No rows" },
  emptyText: { type: String, default: "Nothing here yet." },
});

function blankRow() {
  const row = {};
  for (const col of props.columns) {
    if ("default" in col) row[col.key] = col.default;
    else row[col.key] = col.type === "checkbox" ? false : "";
  }
  return row;
}

function addRow() {
  rows.value = [...rows.value, blankRow()];
}

function removeRow(index) {
  rows.value = rows.value.filter((_, position) => position !== index);
}
</script>
