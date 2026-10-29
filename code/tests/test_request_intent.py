import unittest

from tools.request_intent import (
    RequestIntent,
    classify_request_intent,
)


class RequestIntentTests(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(classify_request_intent(text), expected, text)

    # ---------------------------------------------------------
    # Baseline & Basic Tests
    # ---------------------------------------------------------
    def test_explicit_account_deletion(self):
        self.check(
            "Please delete my account and all personal data.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_data_erasure(self):
        self.check(
            "I want my data erased.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_account_closure(self):
        self.check(
            "Please close my account.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_explicit_negation(self):
        self.check(
            "I do not want you to delete my account; update my phone instead.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_do_not_delete(self):
        self.check(
            "Do not delete my data. I only need an export.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_phone_update_only(self):
        self.check(
            "Please update my phone number.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_surname_correction_only(self):
        self.check(
            "Please correct my surname.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_marketing_opt_out_only(self):
        self.check(
            "Please opt me out of marketing emails.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_marketing_removal_only(self):
        self.check(
            "Remove me from the newsletter mailing list.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_export_only(self):
        self.check(
            "Please export my personal data.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_deletion_plus_export(self):
        self.check(
            "Delete my account and provide a copy of my data.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_correction_plus_deletion(self):
        self.check(
            "Correct my surname and delete my account.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_ambiguous_request(self):
        self.check(
            "I have a request about the information associated with me.",
            RequestIntent.AMBIGUOUS,
        )

    def test_empty_request(self):
        self.check("", RequestIntent.AMBIGUOUS)

    def test_whitespace_request(self):
        self.check("   ", RequestIntent.AMBIGUOUS)

    def test_non_string_input(self):
        self.check(None, RequestIntent.AMBIGUOUS)

    def test_regression_past_participle_and_gerund(self):
        """Regression test ensuring past participle and gerund verbs match deletion patterns."""
        self.check("I want my data erased.", RequestIntent.DELETION_REQUESTED)
        self.check("Have my account deleted immediately.", RequestIntent.DELETION_REQUESTED)
        self.check("I am deleting my profile.", RequestIntent.DELETION_REQUESTED)
        self.check("I want my records wiped completely.", RequestIntent.DELETION_REQUESTED)
        self.check("Ensure my personal data is purged.", RequestIntent.DELETION_REQUESTED)

    # ---------------------------------------------------------
    # Stage 1.1 Extended Regressions: Must classify as DELETION_REQUESTED
    # ---------------------------------------------------------
    def test_permanent_account_deletion_with_treatment(self):
        self.check(
            "Please process a permanent account-deletion request for this email address. Please apply the correct treatment to records covered by the request.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_requesting_deletion_of_account(self):
        self.check(
            "I am requesting deletion of the account registered to this email address.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_close_the_account_completely(self):
        self.check(
            "Please close the account completely.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_close_this_account_permanently(self):
        self.check(
            "Close this account permanently.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_delete_and_export_copy(self):
        self.check(
            "Please delete my account and export a copy of my data.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_tried_to_delete_account_yesterday(self):
        self.check(
            "I tried to delete my account yesterday; please complete the deletion if needed.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_spanish_sample_deletion(self):
        self.check(
            "Intenté eliminar mi cuenta ayer, pero la página terminó mostrando un error. ¿Pueden comprobar si todavía queda algún dato y completar la eliminación si hace falta?",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_french_sample_deletion(self):
        self.check(
            "Je demande la suppression définitive du compte associé à cette adresse e-mail.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_portuguese_sample_deletion(self):
        self.check(
            "Solicito a exclusão permanente da conta associada a este e-mail.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_japanese_sample_deletion(self):
        self.check(
            "このメールアドレスに関連するアカウントの完全な削除を依頼します。",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_korean_sample_deletion(self):
        self.check(
            "이 이메일 주소에 연결된 계정의 영구 삭제를 요청합니다.",
            RequestIntent.DELETION_REQUESTED,
        )

    # ---------------------------------------------------------
    # Stage 1.1 Extended Regressions: Must classify as NOT_A_DELETION_REQUEST
    # ---------------------------------------------------------
    def test_change_email_continue_service(self):
        self.check(
            "Please change the email address used for this account. I want to continue using the service.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_marketing_lists_only(self):
        self.check(
            "Please remove me from marketing lists only. I still want receipts and service messages.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_spanish_non_deletion_negation(self):
        self.check(
            "No quiero eliminar mi cuenta; solo necesito una copia de mis datos.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    # ---------------------------------------------------------
    # Stage 1.1 Extended Regressions: Must remain AMBIGUOUS
    # ---------------------------------------------------------
    def test_policy_inquiry_ambiguous(self):
        self.check(
            "What is your account-deletion policy?",
            RequestIntent.AMBIGUOUS,
        )

    def test_correct_treatment_phrase_not_correction(self):
        """Verifies 'correct treatment' alone is not misinterpreted as an address/profile correction."""
        self.check(
            "Please apply the correct treatment to records.",
            RequestIntent.AMBIGUOUS,
        )

    def test_deletion_plus_secondary_update_or_export(self):
        """Verifies deletion request accompanied by secondary task still classifies as DELETION_REQUESTED."""
        self.check(
            "Delete my account and update my phone number.",
            RequestIntent.DELETION_REQUESTED,
        )
        self.check(
            "Please close my account and provide a copy of my personal data.",
            RequestIntent.DELETION_REQUESTED,
        )

    # ---------------------------------------------------------
    # Stage 1.2 Extended Regressions: Follow-up Deletion & Preservation
    # ---------------------------------------------------------
    def test_followup_investigate_and_finish_deletion(self):
        self.check(
            "I was told deletion was complete, but the account and its "
            "search result can still be found. Please investigate and finish the deletion.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_followup_confirm_profile_is_gone(self):
        self.check(
            "I found an old report saying my account still existed. "
            "Please check the latest state and confirm that the profile is gone.",
            RequestIntent.DELETION_REQUESTED,
        )

    def test_outdated_mobile_replace_and_leave_active(self):
        self.check(
            "The mobile number on my profile is out of date. "
            "Please replace it with the new one and leave the account active.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_invoice_copy_and_preserve_profile(self):
        self.check(
            "I need a copy of last year's invoices for my records. "
            "Please leave my profile and purchase history in place.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_negation_overrides_deletion_verification(self):
        """Explicit negation takes precedence even when text mentions deletion verification."""
        self.check(
            "Do not delete my account; just check whether the profile is gone.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )
        self.check(
            "I do not want deletion, but please verify if my account still exists.",
            RequestIntent.NOT_A_DELETION_REQUEST,
        )

    def test_deletion_with_secondary_invoices_or_field_update(self):
        """A true deletion request accompanied by invoice copy or field update remains DELETION_REQUESTED."""
        self.check(
            "Please delete my account and send me a copy of my invoices.",
            RequestIntent.DELETION_REQUESTED,
        )
        self.check(
            "Please delete my account and replace my mobile number.",
            RequestIntent.DELETION_REQUESTED,
        )


if __name__ == "__main__":
    unittest.main()

