"use client";

import { Disposition } from "../../lib/api";
import { dispositionLabels } from "../../lib/dispositions";

type DispositionSelectProps = {
  value: Disposition;
  onChange: (value: Disposition) => void;
  options: Disposition[];
  label?: string;
};

export default function DispositionSelect({ value, onChange, options, label = "Disposition" }: DispositionSelectProps) {
  return <label>{label}<select value={value} onChange={event => onChange(event.target.value as Disposition)}>{options.map(option => <option key={option} value={option}>{dispositionLabels[option]}</option>)}</select></label>;
}