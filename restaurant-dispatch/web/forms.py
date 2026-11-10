from django import forms

from dispatch.models import ShiftObservation


class ObservationForm(forms.ModelForm):
    """Manually recorded pilot observation. Kept apart from Syncora event data."""

    class Meta:
        model = ShiftObservation
        fields = [
            "source", "service_date", "shift_label", "start_time", "end_time", "covers",
            "waitlist", "waitlist_peak_parties",
            "staff_runners", "staff_bussers", "staff_servers", "staff_hosts", "staff_managers",
            "order_errors", "guest_complaints", "manager_interventions",
            "food_handoff_p90_seconds", "food_handoff_samples", "reset_p90_seconds", "reset_samples",
            "method", "notes",
        ]
        widgets = {
            "service_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "source": "What kind of shift?",
            "covers": "Covers (from the POS or host stand)",
            "waitlist_peak_parties": "Most parties waiting at once",
            "manager_interventions": "Manager interventions (baseline: observer's tally)",
            "food_handoff_p90_seconds": "Baseline food handoff, 90th percentile (seconds)",
            "food_handoff_samples": "Food handoffs timed",
            "reset_p90_seconds": "Baseline reset, 90th percentile (seconds)",
            "reset_samples": "Resets timed",
            "method": "Native tools used and how times were taken",
        }

    def clean(self):
        data = super().clean()
        if data.get("source") == ShiftObservation.SYNCORA:
            # Syncora shifts take their handoff times from event data, never from a stopwatch.
            for name in ("food_handoff_p90_seconds", "food_handoff_samples", "reset_p90_seconds", "reset_samples"):
                data[name] = None
        if data.get("covers") == 0:
            self.add_error("covers", "Enter the covers served during this shift.")
        return data
