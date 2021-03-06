<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns="http://cnx.rice.edu/cnxml"
  xmlns:cnx="http://cnx.rice.edu/cnxml"
  xmlns:md="http://cnx.rice.edu/mdml"
  xmlns:bib="http://bibtexml.sf.net/"
  xmlns:m="http://www.w3.org/1998/Math/MathML"
  xmlns:q="http://cnx.rice.edu/qml/1.0"
  version="1.0"
  exclude-result-prefixes="cnx">

<xsl:output method="xml" encoding="UTF-8" indent="yes"/>

<xsl:strip-space elements="*"/>

<!--
Copy everything, but remove id attributes.
-->

<!-- Default: copy everything (works recursively) -->
<xsl:template match="@*|node()">
  <xsl:copy>
    <xsl:apply-templates select="@*|node()"/>
  </xsl:copy>
</xsl:template>

<!-- remove ids (do nothing with them so that they will disapear) -->
<xsl:template match="@id"/>
<xsl:template match="@alt"/>

</xsl:stylesheet>
