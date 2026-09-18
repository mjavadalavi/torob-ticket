import { BagIcon } from "./icons";
import { localizeTravelValue, toFa } from "@/lib/content";
import { supports } from "@/lib/capabilities";
import { Capability, ModeDetails, OfferAttributes, TravelMode } from "@/lib/types";

type DetailsFor<M extends TravelMode> = Extract<ModeDetails, { mode: M }>;

interface ModePresentation<M extends TravelMode> {
  operatorFilterLabel: string;
  detailTags: (details: DetailsFor<M>, capabilities: Capability[]) => React.ReactNode;
  summaryFeature: (details: DetailsFor<M>, attributes: OfferAttributes) => React.ReactNode;
}

const presentations: { [M in TravelMode]: ModePresentation<M> } = {
  flight: {
    operatorFilterLabel: "شرکت هواپیمایی",
    detailTags: (details) => <>
      <span>{localizeTravelValue(details.fare_type)}</span>
      {details.baggage_allowance_kg != null && (
        <span><BagIcon size={18} /> بار {toFa(details.baggage_allowance_kg)} کیلو</span>
      )}
    </>,
    summaryFeature: (details) => details.baggage_allowance_kg != null
      ? <>بار {toFa(details.baggage_allowance_kg)} کیلو</>
      : null,
  },
  train: {
    operatorFilterLabel: "شرکت ریلی",
    detailTags: (details, capabilities) => <>
      <span>{localizeTravelValue(details.class_name)}</span>
      {details.private_compartment_available === true && <span>کوپه دربست</span>}
      {supports(capabilities, "vehicle_transport") && <span>حمل خودرو</span>}
    </>,
    summaryFeature: (details) => <>{localizeTravelValue(details.class_name)}</>,
  },
  bus: {
    operatorFilterLabel: "شرکت اتوبوس‌رانی",
    detailTags: (details, capabilities) => <>
      <span>{localizeTravelValue(details.bus_class)}</span>
      {supports(capabilities, "seat_selection") && <span>انتخاب صندلی</span>}
    </>,
    summaryFeature: (details) => <>{localizeTravelValue(details.bus_class)}</>,
  },
};

export function operatorFilterLabel(mode: TravelMode) {
  return presentations[mode].operatorFilterLabel;
}

export function ModeDetailTags({ details, capabilities }: { details: ModeDetails; capabilities: Capability[] }) {
  const presentation = presentations[details.mode] as ModePresentation<typeof details.mode>;
  return presentation.detailTags(details as never, capabilities);
}

export function ModeSummaryFeature({
  details,
  attributes,
}: {
  details: ModeDetails;
  attributes: OfferAttributes;
}) {
  const presentation = presentations[details.mode] as ModePresentation<typeof details.mode>;
  return presentation.summaryFeature(details as never, attributes);
}
