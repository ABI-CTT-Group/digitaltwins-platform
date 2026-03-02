<#import "template.ftl" as layout>
<@layout.registrationLayout displayInfo=realm.password && realm.registrationAllowed && !registrationDisabled??; section>
  <#if section = "header">
    ${msg("loginAccountTitle")}
  <#elseif section = "form">
    <div id="kc-form">
      <div id="kc-form-wrapper">
        <div class="dtwins-page-title">DigitalTWINS AI Portal</div>
        <div class="dtwins-card-title">Sign In</div>
        <form id="kc-form-login" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post">
          <#if !usernameHidden??>
            <div class="form-group">
              <label for="username" class="control-label">${msg("usernameOrEmail")}</label>
              <input tabindex="1" id="username" class="form-control" name="username" value="${(login.username!'')}" type="text" autofocus autocomplete="username" />
            </div>
          </#if>

          <div class="form-group">
            <label for="password" class="control-label">${msg("password")}</label>
            <input tabindex="2" id="password" class="form-control" name="password" type="password" autocomplete="current-password" />
          </div>

          <div id="kc-form-options" class="form-group">
            <#if realm.rememberMe && !usernameHidden??>
              <div class="checkbox">
                <label>
                  <#if login.rememberMe??>
                    <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox" checked> ${msg("rememberMe")}
                  <#else>
                    <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox"> ${msg("rememberMe")}
                  </#if>
                </label>
              </div>
            </#if>
            <#if realm.resetPasswordAllowed>
              <span><a tabindex="5" href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")}</a></span>
            </#if>
          </div>

          <div id="kc-form-buttons" class="form-group">
            <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>
            <input tabindex="4" class="btn btn-primary btn-block btn-lg" name="login" id="kc-login" type="submit" value="${msg("doLogIn")}"/>
          </div>

          <#if realm.password && realm.registrationAllowed && !registrationDisabled??>
            <div id="kc-registration">
              <span>${msg("noAccount")} <a tabindex="6" href="${url.registrationUrl}">${msg("doRegister")}</a></span>
            </div>
          </#if>
        </form>
      </div>
    </div>
  <#elseif section = "socialProviders" >
    <#if realm.password && social.providers??>
      <div id="kc-social-providers" class="form-group">
        <div class="dtwins-divider-wrap">
          <hr class="dtwins-divider" />
          <span class="dtwins-or">OR</span>
        </div>
        <ul class="${properties.kcFormSocialAccountListClass!}">
          <#list social.providers as p>
            <li class="${properties.kcFormSocialAccountListItemClass!}">
              <a id="social-${p.alias}" class="${properties.kcFormSocialAccountListButtonClass!} dtwins-idp-btn" type="button" href="${p.loginUrl}">
                <#if p.iconClasses?has_content>
                  <i class="${p.iconClasses!}" aria-hidden="true"></i>
                  <span class="kc-social-icon-text">${p.displayName!}</span>
                <#else>
                  <span class="kc-social-icon-text">${p.displayName!}</span>
                </#if>
              </a>
            </li>
          </#list>
        </ul>
      </div>
    </#if>
  <#elseif section = "info" >
    <#if realm.password && realm.registrationAllowed && !registrationDisabled??>
      <div id="kc-info" class="text-center"></div>
    </#if>
  </#if>
</@layout.registrationLayout>
