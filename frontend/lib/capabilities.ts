import { Capability } from "./types";

export function supports(capabilities: Capability[], capability: Capability) {
  return capabilities.includes(capability);
}

export const capabilityLabels: Record<Capability, string> = {
  refund_rules: "قوانین استرداد",
  seat_selection: "انتخاب صندلی",
  vehicle_transport: "حمل خودرو",
  installment_payment: "پرداخت اقساطی",
  torob_guarantee: "تضمین ترب",
  torob_pay: "ترب‌پی",
};
