/** Public dashboard config — override URLs before Pages deploy. No secrets here. */
window.CASSANDRA_CONFIG = {
  newsletterAction: "", // ConvertKit/Beehiiv form POST URL
  payments: {
    international: {
      stripeSubscribe: "https://buy.stripe.com/PLACEHOLDER",
      stripeDonate: "https://buy.stripe.com/PLACEHOLDER_DONATE",
      paypalDonate: "https://www.paypal.com/donate/?hosted_button_id=PLACEHOLDER",
    },
    my: {
      curlecSubscribe: "https://curlec.com/PLACEHOLDER",
      billplzDonate: "https://www.billplz.com/PLACEHOLDER",
    },
    cn: {
      airwallexSubscribe: "https://checkout.airwallex.com/PLACEHOLDER",
      airwallexDonate: "https://checkout.airwallex.com/PLACEHOLDER_DONATE",
    },
  },
};
