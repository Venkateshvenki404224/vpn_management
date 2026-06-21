<template>
  <Dialog
    v-model:open="open"
    :options="{ title: isEdit ? `Edit ${poolName}` : 'New Pool', size: '2xl' }"
  >
    <template #body-content>
      <div class="space-y-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormControl
            v-model="form.pool_name"
            label="Pool name"
            placeholder="wg0-main"
            :disabled="isEdit"
            required
          />
          <FormControl
            v-model="form.server"
            type="select"
            label="Server"
            :options="serverOptions"
            :placeholder="serverOptions.length ? 'Select a server' : 'No servers available'"
            required
          />
          <FormControl
            v-model="form.cidr"
            label="CIDR"
            placeholder="172.27.0.0/16"
            :disabled="cidrLocked"
            :description="
              cidrLocked
                ? 'Frozen after materialization — create a new pool to change it.'
                : 'Address space to materialize.'
            "
            required
          />
          <FormControl
            v-model="form.gateway_ip"
            label="Gateway IP"
            placeholder="172.27.0.1"
            description="Reserved (never auto-allocated). Usually the .1 of the CIDR."
          />
        </div>

        <Divider />
        <ChildTableEditor
          v-model="form.reserved_ranges"
          label="Reserved ranges"
          :columns="RESERVED_COLUMNS"
          empty-title="No reserved ranges"
          empty-text="Add ranges that must never be auto-allocated (e.g. static hosts)."
        />

        <ErrorMessage :message="errorMessage" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button label="Cancel" @click="close" />
        <Button
          variant="solid"
          theme="gray"
          :label="isEdit ? 'Save' : 'Create pool'"
          :loading="save.loading"
          :disabled="!form.pool_name || !form.server || !form.cidr"
          @click="submit(close)"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import {
  Button,
  Dialog,
  Divider,
  ErrorMessage,
  FormControl,
  createResource,
  toast,
} from "frappe-ui";
import { computed, reactive, watch } from "vue";
import ChildTableEditor from "@/components/ChildTableEditor.vue";

const open = defineModel("open", { type: Boolean, default: false });
const props = defineProps({
  // null/empty => create; a pool name => edit that pool.
  poolName: { type: String, default: null },
});
const emit = defineEmits(["saved"]);

const RESERVED_COLUMNS = [
  { key: "start_ip", label: "Start IP", placeholder: "172.27.0.10" },
  { key: "end_ip", label: "End IP", placeholder: "172.27.0.20" },
  { key: "reason", label: "Reason", placeholder: "static hosts", wide: true },
];

const isEdit = computed(() => Boolean(props.poolName));
// The CIDR can't move once rows are materialized (the controller throws); reflect
// that in the UI so the admin isn't surprised by a rejected save.
const cidrLocked = computed(() => isEdit.value && Number(form.total_addresses) > 0);

function defaults() {
  return {
    pool_name: "",
    server: "",
    cidr: "",
    gateway_ip: "",
    reserved_ranges: [],
    total_addresses: 0,
  };
}
const form = reactive(defaults());

const servers = createResource({ url: "vpn_management.api.list_servers", method: "GET", auto: true });
const serverOptions = computed(() =>
  (servers.data || []).map((server) => ({ label: server.interface_name, value: server.name }))
);

const detail = createResource({
  url: "vpn_management.api.get_pool",
  method: "GET",
  onSuccess: (data) => Object.assign(form, data),
});
const save = createResource({ url: "vpn_management.api.upsert_pool", method: "POST" });
const errorMessage = computed(
  () => save.error?.messages?.join(", ") || save.error?.message || (save.error ? String(save.error) : "")
);

watch(open, (isOpen) => {
  if (!isOpen) return;
  save.reset();
  Object.assign(form, defaults());
  servers.reload();
  if (isEdit.value) detail.fetch({ pool_name: props.poolName });
});

async function submit(close) {
  await save
    .submit({
      pool_name: form.pool_name,
      server: form.server,
      cidr: form.cidr,
      gateway_ip: form.gateway_ip,
      reserved_ranges: form.reserved_ranges,
    })
    .catch(() => {});
  if (save.error) return;
  toast.success(isEdit.value ? "Pool saved" : "Pool created");
  close();
  emit("saved");
}
</script>
