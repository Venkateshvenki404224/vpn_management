<template>
  <Dialog
    v-model:open="open"
    :options="{ title: isEdit ? `Edit ${interfaceName}` : 'New Server', size: '3xl' }"
  >
    <template #body-content>
      <div class="space-y-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormControl
            v-model="form.interface_name"
            label="Interface name"
            placeholder="wg0"
            :disabled="isEdit"
            required
          />
          <FormControl
            v-model.number="form.listen_port"
            type="number"
            label="Listen port"
            placeholder="44556"
          />
          <FormControl
            v-model="form.environment"
            type="select"
            label="Environment"
            :options="ENVIRONMENTS"
          />
          <FormControl
            v-model="form.egress_interface"
            label="Egress interface"
            placeholder="eth0"
          />
          <FormControl
            v-model="form.address_cidr"
            class="sm:col-span-2"
            label="Address CIDR"
            placeholder="172.27.0.1/16"
            description="Computed from the environment when left blank."
          />
        </div>

        <template v-if="isEdit">
          <Divider />
          <ChildTableEditor
            v-model="form.firewall_rules"
            label="Firewall rules"
            :columns="FIREWALL_COLUMNS"
            empty-title="No firewall rules"
            empty-text="Add a rule, or leave empty to disable NAT/forwarding for this interface."
          />
        </template>
        <p
          v-else
          class="rounded-md bg-surface-blue-2 px-3 py-2 text-p-sm text-ink-gray-7"
        >
          Default firewall rules (forwarding, NAT, port redirect) are seeded
          automatically. Edit the server afterwards to customize them.
        </p>

        <ErrorMessage :message="errorMessage" />
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button label="Cancel" @click="close" />
        <Button
          variant="solid"
          theme="gray"
          :label="isEdit ? 'Save' : 'Create server'"
          :loading="save.loading"
          :disabled="!form.interface_name"
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
  // null/empty => create; an interface name => edit that server.
  interfaceName: { type: String, default: null },
});
const emit = defineEmits(["saved"]);

const ENVIRONMENTS = ["dev", "prod"];
const FIREWALL_COLUMNS = [
  {
    key: "rule_type",
    label: "Type",
    type: "select",
    options: ["FORWARD_IN", "FORWARD_OUT", "MASQUERADE", "REDIRECT"],
    default: "FORWARD_IN",
  },
  { key: "ip_table", label: "Table", type: "select", options: ["filter", "nat"], default: "filter" },
  { key: "chain", label: "Chain", placeholder: "FORWARD" },
  { key: "spec", label: "Spec", placeholder: "-i {iface} -j ACCEPT", wide: true },
  { key: "teardown_on_down", label: "Teardown on down", type: "checkbox", default: true },
  { key: "enabled", label: "Enabled", type: "checkbox", default: true },
];

const isEdit = computed(() => Boolean(props.interfaceName));

function defaults() {
  return {
    interface_name: "",
    listen_port: 44556,
    environment: "dev",
    address_cidr: "",
    egress_interface: "eth0",
    firewall_rules: [],
  };
}
const form = reactive(defaults());

const detail = createResource({
  url: "vpn_management.api.get_server",
  method: "GET",
  onSuccess: (data) => Object.assign(form, data),
});
const save = createResource({ url: "vpn_management.api.upsert_server", method: "POST" });
const errorMessage = computed(
  () => save.error?.messages?.join(", ") || save.error?.message || (save.error ? String(save.error) : "")
);

// When the dialog opens, load the server (edit) or reset to defaults (create).
watch(open, (isOpen) => {
  if (!isOpen) return;
  save.reset();
  Object.assign(form, defaults());
  if (isEdit.value) detail.fetch({ interface_name: props.interfaceName });
});

async function submit(close) {
  const params = {
    interface_name: form.interface_name,
    listen_port: form.listen_port,
    environment: form.environment,
    address_cidr: form.address_cidr || undefined,
    egress_interface: form.egress_interface,
  };
  // On create the controller seeds default firewall rules; only send the editor's
  // rows when editing (an empty array on edit deliberately clears them).
  if (isEdit.value) params.firewall_rules = form.firewall_rules;
  await save.submit(params).catch(() => {});
  if (save.error) return;
  toast.success(isEdit.value ? "Server saved" : "Server created");
  close();
  emit("saved");
}
</script>
