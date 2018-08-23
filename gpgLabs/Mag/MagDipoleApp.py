import numpy as np
from scipy.interpolate import interp1d
from SimPEG import Mesh, Utils
from geoana import em
from ipywidgets import widgets
from ipywidgets import Layout
import matplotlib.pyplot as plt


class MagneticDipoleApp(object):
    """docstring for MagneticDipoleApp"""

    mesh = None
    component = None
    z = None
    inclination = None
    declination = None
    length = None
    dx = None
    moment = None
    depth = None
    data = None
    profile = None
    xy_profile = None
    clim = None

    def __init__(self):
        super(MagneticDipoleApp, self).__init__()

    def id_to_cartesian(self, inclination, declination):
        ux = np.cos(inclination/180.*np.pi)*np.sin(declination/180.*np.pi)
        uy = np.cos(inclination/180.*np.pi)*np.cos(declination/180.*np.pi)
        uz = -np.sin(inclination/180.*np.pi)
        return np.r_[ux, uy, uz]

    def dot_product(self, b_vec, orientation):
        b_tmi = np.dot(b_vec, orientation)
        return b_tmi

    def simulate(
        self,
        component, target, inclination, declination,
        length, dx, moment, depth, profile,
        fixed_scale, show_halfwidth
    ):
        self.component = component
        self.target = target
        self.inclination = inclination
        self.declination = declination
        self.length = length
        self.dx = dx
        self.moment = moment
        self.depth = depth
        self.profile = profile
        self.fixed_scale = fixed_scale
        self.show_halfwidth = show_halfwidth

        nT = 1e9
        nx = ny = int(length/dx)
        hx = np.ones(nx)*dx
        hy = np.ones(ny)*dx
        self.mesh = Mesh.TensorMesh((hx, hy), 'CC')
        z = np.r_[1.]
        orientation = self.id_to_cartesian(inclination, declination)
        if self.target == "Dipole":
            md = em.static.MagneticDipoleWholeSpace(
                location=np.r_[0, 0, -depth],
                orientation=orientation,
                moment=moment
            )
        else:
            md = em.static.MagneticPoleWholeSpace(
                location=np.r_[0, 0, -depth],
                orientation=orientation,
                moment=moment
            )
        xyz = Utils.ndgrid(self.mesh.vectorCCx, self.mesh.vectorCCy, z)
        b_vec = md.magnetic_flux_density(xyz)
        # Project to the direction  of earth field
        if component == 'Bt':
            rx_orientation = orientation.copy()
        elif component == 'Bg':
            rx_orientation = orientation.copy()
            xyz_up = Utils.ndgrid(
                self.mesh.vectorCCx, self.mesh.vectorCCy, z+1.
            )
            b_vec -= md.magnetic_flux_density(xyz_up)

        elif component == 'Bx':
            rx_orientation = self.id_to_cartesian(0, 0)
        elif component == 'By':
            rx_orientation = self.id_to_cartesian(0, 90)
        elif component == 'Bz':
            rx_orientation = self.id_to_cartesian(90, 0)

        self.data = self.dot_product(b_vec, rx_orientation) * nT

        # Compute profile
        if profile == "North":
            self.xy_profile = np.c_[
                np.zeros(self.mesh.nCx), self.mesh.vectorCCx
            ]

        elif profile == "East":
            self.xy_profile = np.c_[
                self.mesh.vectorCCx, np.zeros(self.mesh.nCx)
            ]
        self.inds_profile = Utils.closestPoints(self.mesh, self.xy_profile)
        self.data_profile = self.data[self.inds_profile]

    def plot_map(self):
        length = self.length
        data = self.data
        profile = self.profile

        fig = plt.figure(figsize=(5, 6))
        ax1 = plt.subplot2grid((8, 4), (0, 0), rowspan=5, colspan=3)
        ax2 = plt.subplot2grid((8, 4), (6, 0), rowspan=2, colspan=3)

        if (self.clim is None) or (not self.fixed_scale):
            self.clim = data.min(), data.max()

        out = self.mesh.plotImage(
            self.data, pcolorOpts={'cmap': 'jet'}, ax=ax1,
            clim=self.clim
        )
        cax = fig.add_axes([0.75, 0.45, 0.02, 0.5])
        ratio = abs(self.clim[0]/self.clim[1])
        if ratio < 0.05:
            ticks = [self.clim[0], self.clim[1]]
        else:
            ticks = [self.clim[0], 0, self.clim[1]]

        cb = plt.colorbar(
            out[0], ticks=ticks, format="%.3f", cax=cax
        )
        cb.set_label("nT", labelpad=-40, y=-.05, rotation=0)
        ax1.set_aspect(1)
        ax1.set_ylabel("X (North)")
        ax1.set_xlabel("Y (East)")
        if profile == "North":
            xy_profile = np.c_[np.zeros(self.mesh.nCx), self.mesh.vectorCCx]
            ax1.text(1, length/2-length/2*0.1, 'B', color='w')
            ax1.text(1, -length/2, 'A', color='w')
        elif profile == "East":
            xy_profile = np.c_[self.mesh.vectorCCx, np.zeros(self.mesh.nCx)]
            ax1.text(length/2-length/2*0.1, 1, 'B', color='w')
            ax1.text(-length/2, 1, 'A', color='w')

        ax1.plot(self.xy_profile[:, 0], self.xy_profile[:, 1], 'w')
        ax1.set_xticks([])
        ax1.set_yticks([])

        ax2.yaxis.tick_right()
        ax2.plot(self.mesh.vectorCCx, self.data_profile, 'k', lw=2)
        ax2.plot(
            self.mesh.vectorCCx, np.zeros(self.mesh.nCx),
            'k--', color='grey', lw=1
        )

        ax2.set_xlim(-self.length/2., self.length/2.)
        ymin, ymax = ax2.get_ylim()
        ax2.text(-self.length/2., ymax, "A")
        ax2.text(self.length/2.-self.length/2*0.05, ymax, "B")
        ax2.set_yticks([self.clim[0], self.clim[1]])
        if self.show_halfwidth:
            x_half, data_half = self.get_half_width()
            ax2.plot(x_half, data_half, 'bo--')
            ax2.set_xlabel(("Halfwidth: %.1fm")%(abs(np.diff(x_half))))
            # ax2.set_xticks([])
        else:
            ax2.set_xlabel(" ")
        plt.tight_layout()

    def get_half_width(self, n_points=200):
        ind_max = np.argmax(abs(self.data_profile))
        A_half = self.data_profile[ind_max] / 2.
        if self.profile == "North":
            x = self.xy_profile[:, 1]
        else:
            x = self.xy_profile[:, 0]
        f = interp1d(x, self.data_profile)
        x_int = np.linspace(x.min(), x.max(), n_points)
        data_profile_int = f(x_int)
        inds = np.argsort(abs(data_profile_int-A_half))
        ind_first = inds[0]
        for ind in inds:
            dx = abs(x_int[ind_first] - x_int[ind])
            if dx > self.dx:
                ind_second = ind
                break
        inds = [ind_first, ind_second]
        return x_int[inds], data_profile_int[inds]

    def magnetic_dipole_applet(
            self, component, target, inclination, declination,
            length, dx, moment, depth, profile, fixed_scale,
            show_halfwidth
    ):
        self.simulate(
            component, target, inclination, declination,
            length, dx, moment, depth, profile, fixed_scale, show_halfwidth
        )
        self.plot_map()

    def interact_plot_model(self):
        component = widgets.RadioButtons(
            options=["Bt", "Bx", "By", "Bz", "Bg"],
            value='Bt',
            description='field',
            disabled=False
        )
        target = widgets.RadioButtons(
            options=["Dipole", "Monopole"],
            value='Dipole',
            description='target',
            disabled=False,
        )
        inclination = widgets.FloatSlider(description='I', continuous_update=False, min=-90, max=90, step=1, value=0)
        declination = widgets.FloatSlider(description='D', continuous_update=False, min=0, max=180, step=1, value=0)
        length = widgets.FloatSlider(description='length', continuous_update=False, min=50, max=200, step=1, value=72)
        dx = widgets.FloatSlider(description='data spacing', continuous_update=False, min=0.5, max=15, step=0.5, value=2)
        moment = widgets.FloatSlider(description='M', continuous_update=False, min=1, max=100, step=1, value=30)
        depth = widgets.FloatSlider(description='depth', continuous_update=False, min=1, max=50, step=1, value=10)
        profile = widgets.RadioButtons(
            options=["East", "North"],
            value='North',
            description='profile',
            disabled=False
        )
        fixed_scale = widgets.Checkbox(
            value=False,
            description='fixed scale',
            disabled=False,
        )
        show_halfwidth = widgets.Checkbox(
            value=False,
            description='half width',
            disabled=False,
        )
        out = widgets.interactive_output(
            self.magnetic_dipole_applet,
            {
                'component': component,
                'target': target,
                'inclination': inclination,
                'declination': declination,
                'length': length,
                'dx': dx,
                'moment': moment,
                'depth': depth,
                'profile': profile,
                'fixed_scale': fixed_scale,
                'show_halfwidth': show_halfwidth,
            }
        )
        left = widgets.VBox(
            [component, profile],
            layout=Layout(
                width='20%', height='350px', margin='60px 0px 0px 0px'
            )
        )
        right = widgets.VBox(
            [
                target, inclination, declination,
                length, dx, moment, depth, fixed_scale, show_halfwidth
            ],
            layout=Layout(
                width='50%', height='350px', margin='20px 0px 0px 0px'
            )
        )
        image = widgets.VBox(
            [out],
            layout=Layout(
                width='70%', height='350px', margin='0px 0px 0px 0px'
            )
        )
        return widgets.HBox([left, out, right])
